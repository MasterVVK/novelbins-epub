"""
Celery задачи для фоновой обработки
"""
import sys
import os
import signal

# Добавляем пути для импорта парсеров
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded, Terminated
from app import create_app, celery, db
from app.models import Novel, Chapter
from app.services.log_service import LogService
from parsers import create_parser_from_url
import time
import re
from datetime import datetime


# Флаг для отслеживания отмены
_cancel_requested = False


def signal_handler(signum, frame):
    """Обработчик сигнала отмены"""
    global _cancel_requested
    _cancel_requested = True
    raise Terminated("Task cancelled by user")


class CallbackTask(Task):
    """Базовая задача с поддержкой callback и отмены"""

    def __call__(self, *args, **kwargs):
        app = create_app()
        with app.app_context():
            return self.run(*args, **kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Обработка ошибки"""
        app = create_app()
        with app.app_context():
            novel_id = args[0] if args else kwargs.get('novel_id')
            if novel_id:
                novel = Novel.query.get(novel_id)
                if novel:
                    # Не перезаписываем уже установленный статус ошибки
                    # (parsing_error, parsing_timeout, parsing_cancelled)
                    if novel.status not in ['parsing_error', 'parsing_timeout', 'parsing_cancelled']:
                        novel.status = 'error'
                    novel.parsing_task_id = None
                    db.session.commit()


@celery.task(bind=True, base=CallbackTask, soft_time_limit=86400, time_limit=86400)  # 24 часа
def parse_novel_chapters_task(self, novel_id, start_chapter=None, max_chapters=None, use_xvfb=True):
    """
    Фоновая задача парсинга глав новеллы

    Args:
        novel_id: ID новеллы
        start_chapter: Номер главы для начала (None = с начала)
        max_chapters: Максимальное количество глав (None = все)
        use_xvfb: Использовать ли Xvfb (должно быть True для czbooks)
    """
    global _cancel_requested
    _cancel_requested = False

    # Устанавливаем обработчик сигнала SIGTERM для отмены
    old_handler = signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Получаем новеллу
        novel = Novel.query.get(novel_id)
        if not novel:
            raise ValueError(f"Novel {novel_id} not found")

        # Обновляем статус
        novel.status = 'parsing'
        novel.parsing_task_id = self.request.id
        db.session.commit()

        # Логируем начало парсинга
        LogService.log_info(f"🚀 [Novel:{novel_id}] Начинаем парсинг: {novel.title}", novel_id=novel_id)

        # Проверяем количество уже распарсенных глав
        existing_chapters_count = Chapter.query.filter_by(novel_id=novel_id).count()

        # Создаем парсер
        parser = create_parser_from_url(
            novel.source_url,
            auth_cookies=novel.get_auth_cookies() if novel.is_auth_enabled() else None,
            socks_proxy=novel.get_socks_proxy() if novel.is_proxy_enabled() else None,
            headless=False  # Для czbooks нужен non-headless
        )

        # Пытаемся получить список глав с fallback
        self.update_state(state='PROGRESS', meta={'status': 'Получение списка глав', 'progress': 0})
        chapters = None

        try:
            chapters = parser.get_chapter_list(novel.source_url)

            if not chapters:
                raise ValueError("Не удалось получить список глав")

            # Обновляем total_chapters
            novel.total_chapters = len(chapters)
            db.session.commit()

            # Логируем количество глав
            LogService.log_info(f"📚 [Novel:{novel_id}] Найдено глав: {len(chapters)}", novel_id=novel_id)

        except Exception as e:
            # Если не удалось получить список глав (например, Cloudflare блокирует)
            error_msg = str(e)
            is_cloudflare_error = 'Cloudflare' in error_msg or 'Turnstile' in error_msg or 'cookies' in error_msg.lower()

            # Если это ошибка Cloudflare И все главы уже есть → используем fallback
            if is_cloudflare_error and existing_chapters_count > 0 and novel.total_chapters and existing_chapters_count >= novel.total_chapters:
                LogService.log_warning(
                    f"⚠️ [Novel:{novel_id}] Не удалось получить список глав (Cloudflare), но все {existing_chapters_count}/{novel.total_chapters} глав уже в базе. Парсинг завершен.",
                    novel_id=novel_id
                )

                # Закрываем парсер и завершаем успешно
                parser.close()

                # Обновляем статус
                novel.status = 'parsed'
                novel.parsed_chapters = existing_chapters_count
                novel.parsing_task_id = None
                db.session.commit()

                return {
                    'status': 'completed',
                    'message': f'Все главы уже распарсены. В базе {existing_chapters_count} глав. (Cloudflare заблокировал получение списка, но это не критично)',
                    'saved_chapters': existing_chapters_count,
                    'total_chapters': novel.total_chapters
                }
            else:
                # Если не все главы есть или это другая ошибка → пробрасываем исключение
                LogService.log_error(
                    f"❌ [Novel:{novel_id}] Ошибка получения списка глав: {error_msg}. В базе {existing_chapters_count} глав.",
                    novel_id=novel_id
                )
                raise

        # Определяем главы для парсинга
        if start_chapter:
            chapters = chapters[start_chapter - 1:]
        if max_chapters:
            chapters = chapters[:max_chapters]

        total = len(chapters)
        saved_count = 0
        failed_chapters = []  # Список пропущенных глав для повторного парсинга

        # Парсим главы
        for i, ch in enumerate(chapters, 1):
            # Проверяем отмену задачи (через флаг и через БД)
            db.session.refresh(novel)  # Обновляем объект из БД
            if _cancel_requested or novel.status == 'parsing_cancelled':
                LogService.log_warning(f"🛑 [Novel:{novel_id}] Парсинг отменен пользователем. Сохранено {saved_count}/{total} глав", novel_id=novel_id)
                novel.status = 'parsing_cancelled'
                novel.parsing_task_id = None
                db.session.commit()
                parser.close()
                return {
                    'status': 'cancelled',
                    'message': 'Парсинг отменен пользователем',
                    'saved_chapters': saved_count,
                    'total_chapters': total
                }

            chapter_number = start_chapter + i - 1 if start_chapter else i

            # Обновляем прогресс
            progress = int((i / total) * 100)
            self.update_state(
                state='PROGRESS',
                meta={
                    'status': f'Парсинг главы {i}/{total}',
                    'progress': progress,
                    'current_chapter': chapter_number,
                    'saved_chapters': saved_count
                }
            )

            # Проверяем существование
            existing = Chapter.query.filter_by(
                novel_id=novel_id,
                chapter_number=chapter_number
            ).first()

            if existing:
                # Глава уже существует - считаем как успешно обработанную
                saved_count += 1
                continue

            try:
                # Загружаем контент
                content_data = parser.get_chapter_content(ch['url'])
                if not content_data or not content_data.get('content'):
                    continue

                content = content_data['content']

                # Применяем фильтры текста из конфигурации
                if novel.config and novel.config.get('filter_text'):
                    filter_text = novel.config.get('filter_text')
                    # Разбиваем фильтры по строкам
                    filters = [f.strip() for f in filter_text.split('\n') if f.strip()]
                    for filter_pattern in filters:
                        if filter_pattern:
                            original_len = len(content)

                            # Пытаемся применить фильтр напрямую
                            content = content.replace(filter_pattern, '')

                            # Если не сработало, пробуем с нормализацией пробелов и знаков препинания
                            if len(content) == original_len:
                                # Создаем паттерн, где множественные пробелы заменены на \s+
                                # Экранируем спецсимволы regex
                                escaped_pattern = re.escape(filter_pattern)
                                # Заменяем одинарные пробелы на \s+ (один или более пробельных символов)
                                flexible_pattern = escaped_pattern.replace(r'\ ', r'\s+').replace(r'\　', r'\s+')
                                # Делаем восклицательный знак опциональным (не экранирован в escaped_pattern)
                                flexible_pattern = flexible_pattern.replace('！', '[！!]?').replace('!', '[！!]?')
                                # Пробуем найти и удалить с гибким паттерном
                                content = re.sub(flexible_pattern, '', content)

                            if len(content) != original_len:
                                LogService.log_info(
                                    f"🔧 [Novel:{novel_id}, Ch:{chapter_number}] "
                                    f"Применен фильтр: '{filter_pattern}' "
                                    f"(удалено {original_len - len(content)} символов)",
                                    novel_id=novel_id
                                )

                # Создаем главу
                chapter = Chapter(
                    novel_id=novel_id,
                    chapter_number=chapter_number,
                    original_title=ch['title'],
                    url=ch['url'],
                    original_text=content,
                    word_count_original=len(content),
                    status='parsed'
                )
                db.session.add(chapter)
                db.session.commit()

                saved_count += 1
                novel.parsed_chapters = saved_count
                db.session.commit()

                # Автоматическое сохранение cookies после 10 успешных глав
                if saved_count == 10 and hasattr(parser, 'get_cookies'):
                    try:
                        extracted_cookies = parser.get_cookies()
                        if extracted_cookies and not novel.is_auth_enabled():
                            # Сохраняем cookies только если они еще не настроены
                            novel.auth_cookies = extracted_cookies
                            novel.auth_enabled = True
                            db.session.commit()
                            LogService.log_info(
                                f"🍪 [Novel:{novel_id}] Автоматически сохранены cookies из браузера (Cloudflare пройден вручную)",
                                novel_id=novel_id
                            )
                    except Exception as e:
                        LogService.log_warning(f"⚠️ [Novel:{novel_id}] Не удалось сохранить cookies: {e}", novel_id=novel_id)

                # Логируем сохранение главы
                if saved_count % 10 == 0 or saved_count == total:  # Каждую 10-ю главу
                    LogService.log_info(f"📖 [Novel:{novel_id}] Сохранено {saved_count}/{total} глав ({progress}%)", novel_id=novel_id)

            except Exception as e:
                # Логируем ошибку и добавляем в список для повторного парсинга
                LogService.log_warning(f"⚠️ [Novel:{novel_id}, Ch:{chapter_number}] Ошибка: {str(e)}", novel_id=novel_id)
                failed_chapters.append({
                    'chapter_number': chapter_number,
                    'chapter_data': ch,
                    'error': str(e)
                })
                continue

        # ========== ВТОРОЙ ПРОХОД: Повторный парсинг пропущенных глав ==========
        if failed_chapters:
            LogService.log_info(
                f"🔄 [Novel:{novel_id}] Обнаружено {len(failed_chapters)} пропущенных глав. Начинаем повторный парсинг с увеличенным таймаутом...",
                novel_id=novel_id
            )

            # Закрываем старый парсер и создаем новый с увеличенным таймаутом
            parser.close()
            parser = create_parser_from_url(
                novel.source_url,
                auth_cookies=novel.get_auth_cookies() if novel.is_auth_enabled() else None,
                socks_proxy=novel.get_socks_proxy() if novel.is_proxy_enabled() else None,
                headless=False,
                cloudflare_max_attempts=10  # Удвоенное количество попыток (10 вместо 5)
            )

            retry_saved = 0
            still_failed = []

            for failed in failed_chapters:
                chapter_number = failed['chapter_number']
                ch = failed['chapter_data']

                # Проверяем отмену задачи
                db.session.refresh(novel)
                if _cancel_requested or novel.status == 'parsing_cancelled':
                    LogService.log_warning(
                        f"🛑 [Novel:{novel_id}] Повторный парсинг отменен. Успешно: {retry_saved}/{len(failed_chapters)}",
                        novel_id=novel_id
                    )
                    break

                # Обновляем прогресс
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'status': f'Повтор пропущенных: {retry_saved + len(still_failed) + 1}/{len(failed_chapters)}',
                        'progress': int(((saved_count + retry_saved) / total) * 100),
                        'current_chapter': chapter_number,
                        'saved_chapters': saved_count + retry_saved
                    }
                )

                # Проверяем, не была ли глава уже сохранена
                existing = Chapter.query.filter_by(
                    novel_id=novel_id,
                    chapter_number=chapter_number
                ).first()

                if existing:
                    retry_saved += 1
                    continue

                try:
                    LogService.log_info(
                        f"🔄 [Novel:{novel_id}, Ch:{chapter_number}] Повторная попытка парсинга (увеличенный таймаут: 10 попыток × 40s = 400s)",
                        novel_id=novel_id
                    )

                    # Загружаем контент
                    content_data = parser.get_chapter_content(ch['url'])
                    if not content_data or not content_data.get('content'):
                        still_failed.append(failed)
                        continue

                    content = content_data['content']

                    # Применяем фильтры текста
                    if novel.config and novel.config.get('filter_text'):
                        filter_text = novel.config.get('filter_text')
                        filters = [f.strip() for f in filter_text.split('\n') if f.strip()]
                        for filter_pattern in filters:
                            if filter_pattern:
                                original_len = len(content)
                                content = content.replace(filter_pattern, '')
                                if len(content) != original_len:
                                    LogService.log_info(
                                        f"🔧 [Novel:{novel_id}, Ch:{chapter_number}] "
                                        f"Применен фильтр: '{filter_pattern}' "
                                        f"(удалено {original_len - len(content)} символов)",
                                        novel_id=novel_id
                                    )

                    # Создаем главу
                    chapter = Chapter(
                        novel_id=novel_id,
                        chapter_number=chapter_number,
                        original_title=ch['title'],
                        url=ch['url'],
                        original_text=content,
                        word_count_original=len(content),
                        status='parsed'
                    )
                    db.session.add(chapter)
                    db.session.commit()

                    retry_saved += 1
                    saved_count += 1
                    novel.parsed_chapters = saved_count
                    db.session.commit()

                    LogService.log_info(
                        f"✅ [Novel:{novel_id}, Ch:{chapter_number}] Успешно сохранена при повторе ({retry_saved}/{len(failed_chapters)})",
                        novel_id=novel_id
                    )

                except Exception as e:
                    LogService.log_warning(
                        f"❌ [Novel:{novel_id}, Ch:{chapter_number}] Повторная попытка не удалась: {str(e)}",
                        novel_id=novel_id
                    )
                    still_failed.append(failed)

            # Логируем результаты повторного парсинга
            if retry_saved > 0:
                LogService.log_info(
                    f"✅ [Novel:{novel_id}] Повторный парсинг: успешно {retry_saved}/{len(failed_chapters)} глав",
                    novel_id=novel_id
                )

            if still_failed:
                failed_numbers = [str(f['chapter_number']) for f in still_failed]
                LogService.log_warning(
                    f"⚠️ [Novel:{novel_id}] Главы всё ещё не удалось спарсить: {', '.join(failed_numbers)}. "
                    f"Возможно, требуется ручное прохождение Cloudflare через VNC.",
                    novel_id=novel_id
                )

        # Завершаем парсинг
        parser.close()

        # Подсчитываем РЕАЛЬНОЕ количество сохраненных глав из базы
        db.session.refresh(novel)
        actual_saved = Chapter.query.filter_by(novel_id=novel_id).count()

        # Обновляем статус новеллы
        novel.status = 'parsed'
        novel.parsed_chapters = actual_saved
        novel.parsing_task_id = None
        db.session.commit()

        # Формируем итоговое сообщение
        final_message = f'Парсинг завершен. Сохранено {actual_saved} глав из {total}'
        if failed_chapters and 'still_failed' in locals() and len(still_failed) > 0:
            final_message += f' (⚠️ {len(still_failed)} глав не удалось спарсить)'

        # Логируем успешное завершение
        LogService.log_info(f"✅ [Novel:{novel_id}] {final_message}", novel_id=novel_id)

        return {
            'status': 'completed',
            'message': final_message,
            'saved_chapters': actual_saved,
            'total_chapters': total
        }

    except Terminated:
        # Отмена через сигнал
        if 'parser' in locals():
            parser.close()
        novel = Novel.query.get(novel_id)
        if novel:
            saved = saved_count if 'saved_count' in locals() else 0
            total_ch = total if 'total' in locals() else 0
            LogService.log_warning(f"🛑 [Novel:{novel_id}] Парсинг прерван (SIGTERM). Сохранено {saved}/{total_ch} глав", novel_id=novel_id)
            novel.status = 'parsing_cancelled'
            novel.parsing_task_id = None
            db.session.commit()
        return {
            'status': 'cancelled',
            'message': 'Парсинг отменен пользователем',
            'saved_chapters': saved_count if 'saved_count' in locals() else 0,
            'total_chapters': total if 'total' in locals() else 0
        }

    except SoftTimeLimitExceeded:
        if 'parser' in locals():
            parser.close()
        novel = Novel.query.get(novel_id)
        if novel:
            saved = saved_count if 'saved_count' in locals() else 0
            total_ch = total if 'total' in locals() else 0
            LogService.log_error(f"⏱️ [Novel:{novel_id}] Превышено время выполнения парсинга. Сохранено {saved}/{total_ch} глав", novel_id=novel_id)
            novel.status = 'parsing_timeout'
            novel.parsing_task_id = None
            db.session.commit()
        raise

    except Exception as e:
        if 'parser' in locals():
            parser.close()
        novel = Novel.query.get(novel_id)
        if novel:
            saved = saved_count if 'saved_count' in locals() else 0
            total_ch = total if 'total' in locals() else 0
            LogService.log_error(f"❌ [Novel:{novel_id}] Критическая ошибка парсинга: {str(e)}. Сохранено {saved}/{total_ch} глав", novel_id=novel_id)
            novel.status = 'parsing_error'
            novel.parsing_task_id = None
            db.session.commit()
        raise

    finally:
        # Восстанавливаем старый обработчик сигнала
        signal.signal(signal.SIGTERM, old_handler)


@celery.task(bind=True, base=CallbackTask)
def cancel_parsing_task(self, task_id):
    """
    Отмена задачи парсинга

    Args:
        task_id: ID задачи Celery
    """
    try:
        # Отменяем задачу
        celery.control.revoke(task_id, terminate=True, signal='SIGTERM')

        # Находим новеллу с этой задачей
        novel = Novel.query.filter_by(parsing_task_id=task_id).first()
        if novel:
            novel.status = 'parsing_cancelled'
            novel.parsing_task_id = None
            db.session.commit()

        return {
            'status': 'success',
            'message': 'Задача отменена'
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }


@celery.task(bind=True, base=CallbackTask, soft_time_limit=172800, time_limit=172800)  # 48 часов
def edit_novel_chapters_task(self, novel_id, chapter_ids, parallel_threads=3):
    """
    Фоновая задача редактуры глав новеллы

    Args:
        novel_id: ID новеллы
        chapter_ids: Список ID глав для редактуры
        parallel_threads: Количество параллельных потоков (из конфига новеллы)
    """
    from app.services.translator_service import TranslatorService
    from app.services.original_aware_editor_service import OriginalAwareEditorService, EmptyResultError, NoChangesError, RateLimitError
    from app.services.log_service import LogService
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock

    # Флаг для отслеживания отмены
    global _cancel_requested
    _cancel_requested = False

    # Устанавливаем обработчик сигнала SIGTERM для отмены
    old_handler = signal.signal(signal.SIGTERM, signal_handler)

    # Блокировка для безопасного доступа к счетчикам из разных потоков
    counter_lock = Lock()

    try:
        # Получаем новеллу
        novel = Novel.query.get(novel_id)
        if not novel:
            raise ValueError(f"Novel {novel_id} not found")

        # Обновляем статус
        novel.status = 'editing'
        novel.editing_task_id = self.request.id
        db.session.commit()

        # Получаем настройку потоков из конфига новеллы
        if novel.config:
            parallel_threads = novel.config.get('editing_threads', parallel_threads)

        # Инициализируем сервисы
        config = {}
        if novel.config:
            config['model_name'] = novel.config.get('translation_model')
            config['temperature'] = novel.config.get('editing_temperature', novel.config.get('translation_temperature'))

        translator_service = TranslatorService(config=config)
        editor_service = OriginalAwareEditorService(translator_service)

        # Получаем главы
        from app.models import Chapter
        chapters = Chapter.query.filter(Chapter.id.in_(chapter_ids)).order_by(Chapter.chapter_number).all()

        if not chapters:
            raise ValueError("Главы не найдены")

        total_chapters = len(chapters)
        success_count = 0
        processed_count = 0

        self.update_state(state='PROGRESS', meta={'status': 'Начинаем редактуру', 'progress': 0})
        LogService.log_info(f"📝 [Novel:{novel_id}] Начинаем редактуру {total_chapters} глав(ы) в {parallel_threads} потоков", novel_id=novel_id)

        # Функция для редактирования одной главы в отдельном потоке
        def edit_single_chapter(chapter_id):
            nonlocal success_count, processed_count

            # Каждый поток создает свою Flask app context и сессию БД
            from app import create_app
            app = create_app()

            with app.app_context():
                # Загружаем главу и новеллу в контексте текущего потока
                from app.models import Chapter, Novel
                chapter = Chapter.query.get(chapter_id)
                if not chapter:
                    return False

                # ЗАЩИТА ОТ ДУБЛИРОВАНИЯ: Проверяем, не редактируется ли уже глава
                if chapter.status == 'edited':
                    LogService.log_info(f"⏭️ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Уже отредактирована, пропускаем", novel_id=novel_id)
                    with counter_lock:
                        processed_count += 1
                    return False

                novel_check = Novel.query.get(novel_id)

                # Проверяем отмену перед началом
                if _cancel_requested or (novel_check and novel_check.status == 'editing_cancelled'):
                    return None

                # Попытки редактуры с разной логикой retry для разных типов ошибок:
                # - EmptyResultError (API вернул пустой результат): 3 попытки с задержками (0, +5м, +10м)
                # - NoChangesError (текст не изменился): 2 попытки без задержек
                # - Другие ошибки: 3 попытки с задержками

                max_attempts_empty = 3
                max_attempts_no_changes = 2
                retry_delays = [0, 300, 600]  # секунды: 0, 5 мин, 10 мин

                attempt = 0
                empty_result_attempts = 0
                no_changes_attempts = 0

                while True:
                    attempt += 1

                    try:
                        if attempt == 1:
                            LogService.log_info(f"🔄 [Novel:{novel_id}, Ch:{chapter.chapter_number}] Редактирую главу", novel_id=novel_id)
                        else:
                            LogService.log_info(f"🔄 [Novel:{novel_id}, Ch:{chapter.chapter_number}] Попытка {attempt}", novel_id=novel_id)

                        # Создаем отдельный editor_service для этого потока
                        thread_translator = TranslatorService(config=config)
                        thread_editor = OriginalAwareEditorService(thread_translator)

                        result = thread_editor.edit_chapter(chapter)

                        if result:
                            # Успешная редактура
                            with counter_lock:
                                success_count += 1
                                processed_count += 1

                                # Обновляем счетчик в новелле
                                novel_update = Novel.query.get(novel_id)
                                if novel_update:
                                    novel_update.edited_chapters = success_count
                                    db.session.commit()

                            LogService.log_info(f"✅ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Отредактирована ({success_count}/{total_chapters})", novel_id=novel_id)
                            return True
                        else:
                            # Неожиданный return False без исключения - трактуем как общую ошибку
                            raise Exception("edit_chapter вернул False без исключения")

                    except RateLimitError as e:
                        # Достигнут лимит API (часовой/недельный) - ОСТАНАВЛИВАЕМ ВСЮ ЗАДАЧУ
                        LogService.log_error(f"🛑 [Novel:{novel_id}, Ch:{chapter.chapter_number}] {e}", novel_id=novel_id)
                        LogService.log_error(f"🛑 [Novel:{novel_id}] ОСТАНОВКА ЗАДАЧИ: достигнут лимит API", novel_id=novel_id)
                        # Возвращаем специальное значение для остановки всех потоков
                        return 'RATE_LIMIT_STOP'

                    except NoChangesError as e:
                        # Текст не изменился - быстрый retry без задержек (макс 2 попытки)
                        no_changes_attempts += 1
                        if no_changes_attempts < max_attempts_no_changes:
                            LogService.log_warning(f"⚠️ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Текст не изменился, попытка {no_changes_attempts}/{max_attempts_no_changes}. Повтор сразу...", novel_id=novel_id)
                            continue
                        else:
                            # Исчерпаны попытки для NoChangesError - ПРОПУСКАЕМ
                            with counter_lock:
                                processed_count += 1
                            LogService.log_error(f"❌ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Текст не изменился после {max_attempts_no_changes} попыток. Глава ПРОПУЩЕНА.", novel_id=novel_id)
                            return False

                    except EmptyResultError as e:
                        # API вернул пустой результат - retry с задержками (макс 3 попытки)
                        empty_result_attempts += 1
                        if empty_result_attempts < max_attempts_empty:
                            delay_seconds = retry_delays[empty_result_attempts]
                            delay_minutes = delay_seconds // 60
                            LogService.log_warning(f"⚠️ [Novel:{novel_id}, Ch:{chapter.chapter_number}] API вернул пустой результат, попытка {empty_result_attempts}/{max_attempts_empty}. Повтор через {delay_minutes} мин...", novel_id=novel_id)
                            LogService.log_info(f"⏳ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Ожидание {delay_minutes} минут...", novel_id=novel_id)
                            time.sleep(delay_seconds)
                            continue
                        else:
                            # Исчерпаны попытки для EmptyResultError - ПРОПУСКАЕМ
                            with counter_lock:
                                processed_count += 1
                            LogService.log_error(f"❌ [Novel:{novel_id}, Ch:{chapter.chapter_number}] API возвращает пустой результат после {max_attempts_empty} попыток. Глава ПРОПУЩЕНА.", novel_id=novel_id)
                            return False

                    except Exception as e:
                        # Другие ошибки - retry с задержками (макс 3 попытки)
                        if attempt < max_attempts_empty:
                            delay_seconds = retry_delays[attempt]
                            delay_minutes = delay_seconds // 60
                            LogService.log_warning(f"⚠️ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Ошибка: {e}. Попытка {attempt}/{max_attempts_empty}. Повтор через {delay_minutes} мин...", novel_id=novel_id)
                            time.sleep(delay_seconds)
                            continue
                        else:
                            # Все попытки исчерпаны - ПРОПУСКАЕМ главу
                            with counter_lock:
                                processed_count += 1
                            error_msg = f"❌ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Все {max_attempts_empty} попытки завершились ошибками: {e}. Глава ПРОПУЩЕНА."
                            LogService.log_error(error_msg, novel_id=novel_id)
                            return False

        # Многопоточная обработка глав
        with ThreadPoolExecutor(max_workers=parallel_threads) as executor:
            # Запускаем редактирование всех глав (передаем ID, а не объекты)
            future_to_chapter_id = {
                executor.submit(edit_single_chapter, chapter.id): chapter.id
                for chapter in chapters
            }

            # Обрабатываем результаты по мере завершения
            for future in as_completed(future_to_chapter_id):
                chapter_id = future_to_chapter_id[future]

                # Проверяем отмену
                db.session.refresh(novel)
                if _cancel_requested or novel.status == 'editing_cancelled':
                    if novel.status != 'editing_cancelled':
                        novel.status = 'editing_cancelled'
                        novel.editing_task_id = None
                        db.session.commit()

                    # Отменяем все оставшиеся задачи
                    for f in future_to_chapter_id:
                        f.cancel()

                    LogService.log_warning(f"🛑 [Novel:{novel_id}] Редактура отменена пользователем. Отредактировано {success_count}/{total_chapters} глав(ы)", novel_id=novel_id)
                    return {
                        'status': 'cancelled',
                        'message': 'Редактура отменена пользователем',
                        'edited_chapters': success_count,
                        'total_chapters': total_chapters
                    }

                # Получаем результат
                try:
                    result = future.result()

                    # Проверяем на RATE_LIMIT_STOP - нужно остановить ВСЮ задачу
                    if result == 'RATE_LIMIT_STOP':
                        LogService.log_error(f"🛑 [Novel:{novel_id}] Остановка всех потоков из-за достижения лимита API", novel_id=novel_id)

                        # Отменяем все оставшиеся задачи
                        for f in future_to_chapter_id:
                            f.cancel()

                        # Устанавливаем статус ошибки
                        novel.status = 'editing_error'
                        novel.editing_task_id = None
                        db.session.commit()

                        return {
                            'status': 'rate_limit',
                            'message': f'Редактура остановлена: достигнут лимит API. Отредактировано {success_count}/{total_chapters} глав.',
                            'edited_chapters': success_count,
                            'total_chapters': total_chapters
                        }

                    # Обновляем прогресс
                    with counter_lock:
                        progress = int((processed_count / total_chapters) * 100)
                        self.update_state(
                            state='PROGRESS',
                            meta={
                                'status': f'Редактура: {processed_count}/{total_chapters} глав',
                                'progress': progress,
                                'edited_chapters': success_count
                            }
                        )
                except Exception as e:
                    LogService.log_error(f"Ошибка получения результата для главы ID={chapter_id}: {e}", novel_id=novel_id)

        # Обновляем статус новеллы в зависимости от результата
        if success_count > 0:
            novel.status = 'edited'
            completion_msg = f'🎉 [Novel:{novel_id}] Редактура завершена: {success_count}/{total_chapters} глав(ы) отредактировано'
            LogService.log_info(completion_msg, novel_id=novel_id)
        else:
            novel.status = 'editing_error'
            error_msg = f'❌ [Novel:{novel_id}] Редактура завершена БЕЗ УСПЕШНЫХ РЕЗУЛЬТАТОВ: 0/{total_chapters} глав отредактировано'
            LogService.log_error(error_msg, novel_id=novel_id)

        novel.editing_task_id = None
        db.session.commit()

        return {
            'status': 'completed' if success_count > 0 else 'failed',
            'message': f'Редактура завершена. Отредактировано {success_count} глав из {total_chapters}',
            'edited_chapters': success_count,
            'total_chapters': total_chapters
        }

    except Terminated:
        # Отмена через сигнал
        novel = Novel.query.get(novel_id)
        if novel:
            novel.status = 'editing_cancelled'
            novel.editing_task_id = None
            db.session.commit()
        LogService.log_warning(f"🛑 [Novel:{novel_id}] Редактура прервана по сигналу SIGTERM", novel_id=novel_id)
        return {
            'status': 'cancelled',
            'message': 'Редактура отменена пользователем',
            'edited_chapters': success_count if 'success_count' in locals() else 0,
            'total_chapters': total_chapters if 'total_chapters' in locals() else 0
        }

    except SoftTimeLimitExceeded:
        novel = Novel.query.get(novel_id)
        if novel:
            novel.status = 'editing_timeout'
            novel.editing_task_id = None
            db.session.commit()
        LogService.log_error(f"⏱️ [Novel:{novel_id}] Превышено время выполнения задачи редактуры (48 часов)", novel_id=novel_id)
        raise

    except Exception as e:
        novel = Novel.query.get(novel_id)
        if novel:
            novel.status = 'editing_error'
            novel.editing_task_id = None
            db.session.commit()
        LogService.log_error(f"❌ [Novel:{novel_id}] Критическая ошибка редактуры: {str(e)}", novel_id=novel_id)
        raise

    finally:
        # Восстанавливаем старый обработчик сигнала
        signal.signal(signal.SIGTERM, old_handler)

        # Гарантированно очищаем editing_task_id даже если что-то пошло не так
        try:
            novel = Novel.query.get(novel_id)
            if novel and novel.editing_task_id == self.request.id:
                novel.editing_task_id = None
                db.session.commit()
        except:
            pass  # Игнорируем ошибки при очистке


@celery.task(bind=True, base=CallbackTask)
def cancel_editing_task(self, task_id):
    """
    Отмена задачи редактуры

    Args:
        task_id: ID задачи Celery
    """
    try:
        # Отменяем задачу через Celery
        celery.control.revoke(task_id, terminate=True, signal='SIGTERM')

        # Находим новеллу с этой задачей
        novel = Novel.query.filter_by(editing_task_id=task_id).first()
        if novel:
            novel.status = 'editing_cancelled'
            novel.editing_task_id = None
            db.session.commit()

        return {
            'status': 'success',
            'message': 'Задача редактуры отменена'
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }


@celery.task(bind=True, base=CallbackTask, soft_time_limit=172800, time_limit=172800)  # 48 часов
def align_novel_chapters_task(self, novel_id, chapter_ids, parallel_threads=3):
    """
    Фоновая задача билингвального выравнивания глав новеллы

    Args:
        novel_id: ID новеллы
        chapter_ids: Список ID глав для выравнивания
        parallel_threads: Количество параллельных потоков (из конфига новеллы)
    """
    from app.services.bilingual_alignment_service import BilingualAlignmentService
    from app.services.log_service import LogService
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock

    # Флаг для отслеживания отмены
    global _cancel_requested
    _cancel_requested = False

    # Устанавливаем обработчик сигнала SIGTERM
    old_handler = signal.signal(signal.SIGTERM, signal_handler)

    # Блокировка для thread-safe доступа к счётчикам
    counter_lock = Lock()

    try:
        # Получаем новеллу
        novel = Novel.query.get(novel_id)
        if not novel:
            raise ValueError(f"Novel {novel_id} not found")

        # Обновляем статус
        novel.status = 'aligning'
        novel.alignment_task_id = self.request.id
        db.session.commit()

        # Получаем настройку потоков из конфига новеллы
        if novel.config:
            parallel_threads = novel.config.get('alignment_threads', parallel_threads)

        # Получаем главы
        from app.models import Chapter
        chapters = Chapter.query.filter(Chapter.id.in_(chapter_ids)).order_by(Chapter.chapter_number).all()

        if not chapters:
            raise ValueError("Главы не найдены")

        total_chapters = len(chapters)
        success_count = 0
        processed_count = 0

        self.update_state(state='PROGRESS', meta={'status': 'Начинаем выравнивание', 'progress': 0})
        LogService.log_info(
            f"🔗 [Novel:{novel_id}] Начинаем билингвальное выравнивание {total_chapters} глав(ы) в {parallel_threads} потоков",
            novel_id=novel_id
        )

        # Функция для выравнивания одной главы в отдельном потоке
        def align_single_chapter(chapter_id):
            nonlocal success_count, processed_count

            # Каждый поток создает свою Flask app context и сессию БД
            from app import create_app
            app = create_app()

            with app.app_context():
                # Загружаем главу и новеллу в контексте текущего потока
                from app.models import Chapter, Novel
                from app.models.bilingual_alignment import BilingualAlignment

                chapter = Chapter.query.get(chapter_id)
                if not chapter:
                    return False

                # ЗАЩИТА ОТ ДУБЛИРОВАНИЯ: Проверяем alignment и статус главы
                existing_alignment = BilingualAlignment.query.filter_by(chapter_id=chapter_id).first()

                # Пропускаем только если alignment существует И статус = 'aligned'
                if existing_alignment and chapter.status == 'aligned':
                    LogService.log_info(
                        f"✅ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Выравнивание уже существует (пропускаем)",
                        novel_id=novel_id,
                        chapter_id=chapter_id
                    )
                    with counter_lock:
                        processed_count += 1
                        success_count += 1
                    return True

                # Если alignment существует, но статус изменен - пересоздаем
                if existing_alignment and chapter.status != 'aligned':
                    BilingualAlignment.query.filter_by(chapter_id=chapter_id).delete()
                    db.session.commit()
                    LogService.log_info(
                        f"🔄 [Novel:{novel_id}, Ch:{chapter.chapter_number}] Статус изменен на '{chapter.status}', пересоздаем сопоставление",
                        novel_id=novel_id,
                        chapter_id=chapter_id
                    )

                # Проверка отмены задачи (без лога - главный лог в основном цикле)
                novel_fresh = Novel.query.get(novel_id)
                if _cancel_requested or novel_fresh.status == 'alignment_cancelled':
                    return False

                try:
                    # Создаём сервис в контексте потока
                    service = BilingualAlignmentService(
                        template_id=novel_fresh.bilingual_template_id,
                        model_id=None
                    )

                    LogService.log_info(
                        f"🔗 [Novel:{novel_id}, Ch:{chapter.chapter_number}] Начинаем выравнивание",
                        novel_id=novel_id,
                        chapter_id=chapter_id
                    )

                    start_time = datetime.now()

                    # ВЫРАВНИВАНИЕ ГЛАВЫ
                    alignments = service.align_chapter(
                        chapter=chapter,
                        force_refresh=False,  # Не пересоздавать если есть
                        save_to_cache=True
                    )

                    duration = (datetime.now() - start_time).total_seconds()

                    if alignments:
                        # Обновляем статус главы на 'aligned'
                        chapter.status = 'aligned'

                        # Обновляем счётчик в новелле (thread-safe)
                        with counter_lock:
                            novel_fresh.aligned_chapters = Novel.query.get(novel_id).aligned_chapters or 0
                            novel_fresh.aligned_chapters += 1
                            db.session.commit()
                            processed_count += 1
                            success_count += 1

                        LogService.log_info(
                            f"✅ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Выравнивание завершено за {duration:.1f}с ({len(alignments)} пар) → status='aligned'",
                            novel_id=novel_id,
                            chapter_id=chapter_id
                        )
                        return True
                    else:
                        LogService.log_error(
                            f"❌ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Выравнивание вернуло пустой результат",
                            novel_id=novel_id,
                            chapter_id=chapter_id
                        )
                        with counter_lock:
                            processed_count += 1
                        return False

                except Exception as e:
                    LogService.log_error(
                        f"❌ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Ошибка выравнивания: {e}",
                        novel_id=novel_id,
                        chapter_id=chapter_id
                    )
                    with counter_lock:
                        processed_count += 1
                    return False

        # Параллельное выравнивание глав
        LogService.log_info(
            f"🚀 [Novel:{novel_id}] Запускаем {parallel_threads} потоков для выравнивания {total_chapters} глав",
            novel_id=novel_id
        )

        with ThreadPoolExecutor(max_workers=parallel_threads) as executor:
            # НЕ подаём все задачи сразу - подаём итеративно для возможности быстрой отмены
            pending_ids = list(chapter_ids)  # Очередь глав на обработку
            futures = {}  # Активные futures
            cancelled = False

            while pending_ids or futures:
                # ПРОВЕРКА ОТМЕНЫ: Не подаём новые задачи
                if _cancel_requested and not cancelled:
                    cancelled = True
                    remaining = len(pending_ids)
                    LogService.log_warning(
                        f"🛑 [Novel:{novel_id}] Обнаружен запрос отмены, пропускаем {remaining} оставшихся глав",
                        novel_id=novel_id
                    )
                    pending_ids.clear()  # Очищаем очередь - не будем подавать новые
                    # Отменяем ожидающие futures
                    for f in futures:
                        if not f.done():
                            f.cancel()

                # Подаём новые задачи пока есть слоты и главы в очереди
                while pending_ids and len(futures) < parallel_threads:
                    ch_id = pending_ids.pop(0)
                    future = executor.submit(align_single_chapter, ch_id)
                    futures[future] = ch_id

                # Если нет активных задач - выходим
                if not futures:
                    break

                # Ждём завершения хотя бы одной задачи
                done_futures = [f for f in futures if f.done()]
                if not done_futures:
                    import time
                    time.sleep(0.1)
                    continue

                # Обрабатываем завершённые задачи
                for future in done_futures:
                    chapter_id = futures.pop(future)

                    try:
                        result = future.result()

                        # Обновляем прогресс
                        progress = int((processed_count / total_chapters) * 100)
                        self.update_state(
                            state='PROGRESS',
                            meta={
                                'status': f'Обработано {processed_count}/{total_chapters} глав',
                                'progress': progress,
                                'success_count': success_count,
                                'processed_count': processed_count
                            }
                        )

                        # Логируем прогресс каждые 10%
                        if processed_count % max(1, total_chapters // 10) == 0:
                            LogService.log_info(
                                f"📊 [Novel:{novel_id}] Прогресс выравнивания: {processed_count}/{total_chapters} ({progress}%) | Успешно: {success_count}",
                                novel_id=novel_id
                            )

                    except Exception as e:
                        LogService.log_error(
                            f"❌ [Novel:{novel_id}] Ошибка в потоке выравнивания: {e}",
                            novel_id=novel_id
                        )

        # Финальный статус
        if _cancel_requested:
            # Если была отмена - оставляем статус alignment_cancelled
            LogService.log_warning(
                f"🛑 [Novel:{novel_id}] Выравнивание отменено. Обработано: {success_count}/{total_chapters} глав",
                novel_id=novel_id
            )
            # Статус уже установлен в alignment_cancelled через API
        elif success_count == total_chapters:
            novel.status = 'completed'
            LogService.log_info(
                f"✅ [Novel:{novel_id}] Выравнивание завершено успешно: {success_count}/{total_chapters} глав",
                novel_id=novel_id
            )
        else:
            novel.status = 'partial_alignment'
            LogService.log_warning(
                f"⚠️ [Novel:{novel_id}] Выравнивание завершено частично: {success_count}/{total_chapters} глав",
                novel_id=novel_id
            )

        novel.alignment_task_id = None
        db.session.commit()

        return {
            'status': 'completed',
            'total': total_chapters,
            'success': success_count,
            'failed': total_chapters - success_count
        }

    except Exception as e:
        LogService.log_error(f"❌ [Novel:{novel_id}] Критическая ошибка выравнивания: {e}", novel_id=novel_id)

        # Обновляем статус на ошибку
        novel = Novel.query.get(novel_id)
        if novel:
            novel.status = 'alignment_error'
            novel.alignment_task_id = None
            db.session.commit()

        raise

    finally:
        # Восстанавливаем старый обработчик сигнала
        signal.signal(signal.SIGTERM, old_handler)

        # Гарантированно очищаем alignment_task_id даже если что-то пошло не так
        try:
            novel = Novel.query.get(novel_id)
            if novel and novel.alignment_task_id == self.request.id:
                novel.alignment_task_id = None
                db.session.commit()
        except:
            pass  # Игнорируем ошибки при очистке


@celery.task(bind=True, base=CallbackTask, soft_time_limit=86400, time_limit=86400)  # 24 часа
def generate_bilingual_epub_task(self, novel_id):
    """
    Фоновая задача генерации двуязычного EPUB

    Args:
        novel_id: ID новеллы
    """
    from app.services.epub_service import EPUBService
    from app.services.log_service import LogService
    from flask import current_app

    # Флаг для отслеживания отмены
    global _cancel_requested
    _cancel_requested = False

    # Устанавливаем обработчик сигнала SIGTERM для отмены
    old_handler = signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Получаем новеллу
        novel = Novel.query.get(novel_id)
        if not novel:
            raise ValueError(f"Novel {novel_id} not found")

        # Обновляем статус
        novel.status = 'generating_epub'
        novel.epub_generation_task_id = self.request.id
        db.session.commit()

        self.update_state(state='PROGRESS', meta={'status': 'Начинаем генерацию EPUB', 'progress': 0})
        LogService.log_info(f"📚 [Novel:{novel_id}] Начинаем генерацию двуязычного EPUB для '{novel.title}'", novel_id=novel_id)

        # Получаем главы для EPUB
        from app.models import Chapter
        chapters = Chapter.query.filter_by(novel_id=novel_id).order_by(Chapter.chapter_number).all()

        if not chapters:
            raise ValueError("Нет глав для генерации EPUB")

        # Подготовка данных для EPUB
        chapters_data = []
        for chapter in chapters:
            # Используем отредактированный текст, если есть, иначе переведенный
            edited_trans = chapter.edited_translation
            current_trans = chapter.current_translation

            content = None
            title = None

            if edited_trans:
                content = edited_trans.translated_text
                title = edited_trans.translated_title
            elif current_trans:
                content = current_trans.translated_text
                title = current_trans.translated_title

            if content:  # Только главы с контентом
                chapters_data.append({
                    'number': chapter.chapter_number,
                    'title': title or chapter.original_title or f'Глава {chapter.chapter_number}',
                    'content': content
                })

        if not chapters_data:
            raise ValueError("Нет переведенных глав для генерации EPUB")

        LogService.log_info(
            f"📖 [Novel:{novel_id}] Подготовлено {len(chapters_data)} глав для EPUB",
            novel_id=novel_id
        )

        # Проверка отмены
        if _cancel_requested or novel.status == 'epub_generation_cancelled':
            LogService.log_info(f"⏹️ [Novel:{novel_id}] Генерация EPUB отменена пользователем", novel_id=novel_id)
            novel.status = 'epub_generation_cancelled'
            db.session.commit()
            return {'status': 'cancelled'}

        # Конфигурация EPUB
        epub_config = {
            'language': 'ru',
            'mode': 'bilingual',  # Двуязычный режим
            'include_toc': True,
            'include_cover': True
        }

        # Создаем EPUBService с Flask app
        from app import create_app
        app = create_app()
        epub_service = EPUBService(app)

        # Генерируем EPUB
        self.update_state(state='PROGRESS', meta={'status': 'Генерируем EPUB файл', 'progress': 50})

        epub_path = epub_service.create_bilingual_epub(
            novel_id=novel_id,
            chapters=chapters_data,
            config=epub_config
        )

        if not epub_path or not os.path.exists(epub_path):
            raise ValueError("EPUB файл не был создан")

        # Проверка отмены после генерации
        novel = Novel.query.get(novel_id)
        if _cancel_requested or novel.status == 'epub_generation_cancelled':
            LogService.log_info(f"⏹️ [Novel:{novel_id}] Генерация EPUB отменена после создания файла", novel_id=novel_id)
            # Удаляем созданный файл
            if os.path.exists(epub_path):
                os.remove(epub_path)
            novel.status = 'epub_generation_cancelled'
            db.session.commit()
            return {'status': 'cancelled'}

        # Успешное завершение
        file_size = os.path.getsize(epub_path) / (1024 * 1024)  # MB
        LogService.log_info(
            f"✅ [Novel:{novel_id}] Двуязычный EPUB успешно создан: {os.path.basename(epub_path)} ({file_size:.2f} MB)",
            novel_id=novel_id
        )

        novel.status = 'epub_generated'
        novel.epub_path = epub_path
        db.session.commit()

        self.update_state(state='SUCCESS', meta={
            'status': 'EPUB успешно создан',
            'progress': 100,
            'epub_path': epub_path,
            'file_size_mb': round(file_size, 2)
        })

        return {
            'status': 'success',
            'epub_path': epub_path,
            'file_size_mb': round(file_size, 2),
            'chapters_count': len(chapters_data)
        }

    except Terminated:
        LogService.log_info(f"⏹️ [Novel:{novel_id}] Генерация EPUB прервана (SIGTERM)", novel_id=novel_id)
        novel = Novel.query.get(novel_id)
        if novel:
            novel.status = 'epub_generation_cancelled'
            db.session.commit()
        raise

    except Exception as e:
        LogService.log_error(f"❌ [Novel:{novel_id}] Ошибка генерации EPUB: {e}", novel_id=novel_id)
        novel = Novel.query.get(novel_id)
        if novel:
            novel.status = 'epub_generation_error'
            db.session.commit()
        raise

    finally:
        # Восстанавливаем старый обработчик сигнала
        signal.signal(signal.SIGTERM, old_handler)

        # Гарантированно очищаем epub_generation_task_id даже если что-то пошло не так
        try:
            novel = Novel.query.get(novel_id)
            if novel and novel.epub_generation_task_id == self.request.id:
                novel.epub_generation_task_id = None
                db.session.commit()
        except:
            pass  # Игнорируем ошибки при очистке
