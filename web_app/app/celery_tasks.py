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

        # Создаем парсер
        parser = create_parser_from_url(
            novel.source_url,
            auth_cookies=novel.get_auth_cookies() if novel.is_auth_enabled() else None,
            socks_proxy=novel.get_socks_proxy() if novel.is_proxy_enabled() else None,
            headless=False  # Для czbooks нужен non-headless
        )

        # Получаем список глав
        self.update_state(state='PROGRESS', meta={'status': 'Получение списка глав', 'progress': 0})
        chapters = parser.get_chapter_list(novel.source_url)

        if not chapters:
            raise ValueError("Не удалось получить список глав")

        # Обновляем total_chapters
        novel.total_chapters = len(chapters)
        db.session.commit()

        # Логируем количество глав
        LogService.log_info(f"📚 [Novel:{novel_id}] Найдено глав: {len(chapters)}", novel_id=novel_id)

        # Определяем главы для парсинга
        if start_chapter:
            chapters = chapters[start_chapter - 1:]
        if max_chapters:
            chapters = chapters[:max_chapters]

        total = len(chapters)
        saved_count = 0

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
                # Логируем ошибку, но продолжаем
                LogService.log_warning(f"⚠️ [Novel:{novel_id}, Ch:{chapter_number}] Ошибка: {str(e)}", novel_id=novel_id)
                continue

        # Завершаем парсинг
        parser.close()

        # Обновляем статус новеллы
        novel.status = 'parsed'
        novel.parsing_task_id = None
        db.session.commit()

        # Логируем успешное завершение
        LogService.log_info(f"✅ [Novel:{novel_id}] Парсинг завершен успешно! Сохранено {saved_count} глав из {total}", novel_id=novel_id)

        return {
            'status': 'completed',
            'message': f'Парсинг завершен. Сохранено {saved_count} глав из {total}',
            'saved_chapters': saved_count,
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


# Глобальный словарь для хранения экземпляров ParallelEditorService по task_id
_editor_services = {}


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
    from app.services.original_aware_editor_service import OriginalAwareEditorService
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

                # Попытки редактуры с повтором при неудаче
                max_attempts = 2

                for attempt in range(1, max_attempts + 1):
                    try:
                        if attempt == 1:
                            LogService.log_info(f"🔄 [Novel:{novel_id}, Ch:{chapter.chapter_number}] Редактирую главу", novel_id=novel_id)
                        else:
                            LogService.log_info(f"🔄 [Novel:{novel_id}, Ch:{chapter.chapter_number}] Попытка {attempt}/{max_attempts}", novel_id=novel_id)

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
                            # Редактура не удалась (текст не изменился)
                            if attempt < max_attempts:
                                LogService.log_warning(f"⚠️ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Попытка {attempt}/{max_attempts} не удалась (текст не изменился). Повторяем...", novel_id=novel_id)
                                continue
                            else:
                                # Последняя попытка не удалась - принимаем как есть
                                LogService.log_warning(f"⚠️ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Все {max_attempts} попытки не удались. Принимаем текст как есть.", novel_id=novel_id)

                                # Сохраняем переведенный текст как отредактированный
                                from app.models import Translation
                                initial_translation = Translation.query.filter_by(
                                    chapter_id=chapter.id,
                                    translation_type='initial'
                                ).order_by(Translation.created_at.desc()).first()

                                if initial_translation:
                                    edited_translation = Translation(
                                        chapter_id=chapter.id,
                                        translated_title=initial_translation.translated_title,
                                        translated_text=initial_translation.translated_text,  # Копируем переведенный текст
                                        translation_type='edited',
                                        api_used='ollama',
                                        model_used=config.get('ai_model', {}).get('name', 'unknown'),
                                        quality_score=5,  # Средняя оценка для неизмененного текста
                                        translation_time=0.0
                                    )
                                    db.session.add(edited_translation)

                                    # Обновляем edited_text главы
                                    chapter.edited_text = initial_translation.translated_text

                                # Обновляем статус главы на 'edited'
                                chapter.status = 'edited'
                                db.session.commit()

                                with counter_lock:
                                    success_count += 1
                                    processed_count += 1

                                    novel_update = Novel.query.get(novel_id)
                                    if novel_update:
                                        novel_update.edited_chapters = success_count
                                        db.session.commit()

                                LogService.log_info(f"✅ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Принята без изменений ({success_count}/{total_chapters})", novel_id=novel_id)
                                return True

                    except Exception as e:
                        if attempt < max_attempts:
                            LogService.log_warning(f"⚠️ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Ошибка на попытке {attempt}/{max_attempts}: {e}. Повторяем...", novel_id=novel_id)
                            continue
                        else:
                            # Все попытки исчерпаны
                            with counter_lock:
                                processed_count += 1
                            error_msg = f"❌ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Все {max_attempts} попытки завершились ошибками: {e}"
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
