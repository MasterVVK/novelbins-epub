"""
API endpoints для управления генерацией EPUB через Celery
"""
from flask import Blueprint, request, jsonify
from app.models import Novel
from app import db, celery
from app.celery_tasks import generate_bilingual_epub_task

epub_generation_bp = Blueprint('epub_generation', __name__)


@epub_generation_bp.route('/novels/<int:novel_id>/generate-epub', methods=['POST'])
def generate_epub(novel_id):
    """
    Запуск генерации двуязычного EPUB для новеллы
    """
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        # Проверяем что уже не запущена генерация
        if novel.epub_generation_task_id:
            return jsonify({
                'success': False,
                'error': 'Генерация EPUB уже запущена'
            }), 400

        # Запускаем Celery задачу
        task = generate_bilingual_epub_task.apply_async(
            args=[novel_id],
            queue='czbooks_queue'
        )

        # Сохраняем task_id
        novel.epub_generation_task_id = task.id
        novel.status = 'generating_epub'
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Генерация EPUB запущена',
            'task_id': task.id
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@epub_generation_bp.route('/novels/<int:novel_id>/generate-epub/cancel', methods=['POST'])
def cancel_epub_generation(novel_id):
    """
    Отмена генерации EPUB
    """
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        if not novel.epub_generation_task_id:
            return jsonify({
                'success': False,
                'error': 'Генерация EPUB не запущена'
            }), 400

        # Отменяем задачу через celery.control.revoke
        task_id = novel.epub_generation_task_id
        celery.control.revoke(task_id, terminate=True, signal='SIGTERM')

        # Обновляем статус
        novel.status = 'epub_generation_cancelled'
        novel.epub_generation_task_id = None
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Генерация EPUB отменена',
            'task_id': task_id
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@epub_generation_bp.route('/novels/<int:novel_id>/generate-epub/status', methods=['GET'])
def get_epub_generation_status(novel_id):
    """
    Получение статуса генерации EPUB
    """
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        if not novel.epub_generation_task_id:
            return jsonify({
                'success': True,
                'is_running': False,
                'status': novel.status
            })

        # Получаем статус задачи из Celery
        from celery.result import AsyncResult
        task = AsyncResult(novel.epub_generation_task_id, app=celery)

        return jsonify({
            'success': True,
            'is_running': True,
            'task_id': novel.epub_generation_task_id,
            'task_state': task.state,
            'task_info': task.info if task.info else {},
            'novel_status': novel.status
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
