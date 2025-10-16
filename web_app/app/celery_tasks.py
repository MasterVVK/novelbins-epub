"""
Celery задачи для фоновой обработки
"""
import sys
import os
import signal

# Добавляем пути для импорта парсеров
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded, Terminated
from app import create_app, celery, db
from app.models import Novel, Chapter
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

        # Определяем главы для парсинга
        if start_chapter:
            chapters = chapters[start_chapter - 1:]
        if max_chapters:
            chapters = chapters[:max_chapters]

        total = len(chapters)
        saved_count = 0

        # Парсим главы
        for i, ch in enumerate(chapters, 1):
            # Проверяем отмену задачи
            if _cancel_requested:
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

            except Exception as e:
                # Логируем ошибку, но продолжаем
                print(f"Ошибка при парсинге главы {chapter_number}: {str(e)}")
                continue

        # Завершаем парсинг
        parser.close()

        # Обновляем статус новеллы
        novel.status = 'parsed'
        novel.parsing_task_id = None
        db.session.commit()

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
            novel.status = 'parsing_timeout'
            novel.parsing_task_id = None
            db.session.commit()
        raise

    except Exception as e:
        if 'parser' in locals():
            parser.close()
        novel = Novel.query.get(novel_id)
        if novel:
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
