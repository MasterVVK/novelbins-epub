"""
API endpoints для управления парсингом через Celery
"""
from flask import Blueprint, request, jsonify
from app.models import Novel
from app import db, celery
from app.celery_tasks import parse_novel_chapters_task, cancel_parsing_task

parsing_bp = Blueprint('parsing', __name__)


@parsing_bp.route('/novels/<int:novel_id>/parse', methods=['POST'])
def start_parsing(novel_id):
    """
    Запуск парсинга новеллы через Celery

    Body:
    {
        "start_chapter": 1 (optional),
        "max_chapters": 10 (optional)
    }
    """
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        # Проверяем, не запущен ли уже парсинг
        if novel.parsing_task_id:
            task = celery.AsyncResult(novel.parsing_task_id)
            if task.state in ['PENDING', 'STARTED', 'PROGRESS']:
                return jsonify({
                    'success': False,
                    'error': 'Парсинг уже выполняется',
                    'task_id': novel.parsing_task_id,
                    'state': task.state
                }), 400

        # Получаем параметры
        data = request.get_json() or {}
        start_chapter = data.get('start_chapter')
        max_chapters = data.get('max_chapters')

        # Запускаем задачу в очереди czbooks_queue
        task = parse_novel_chapters_task.apply_async(
            kwargs={
                'novel_id': novel_id,
                'start_chapter': start_chapter,
                'max_chapters': max_chapters,
                'use_xvfb': True
            },
            queue='czbooks_queue'
        )

        # Сохраняем task_id
        novel.parsing_task_id = task.id
        novel.status = 'parsing'
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Парсинг запущен',
            'task_id': task.id,
            'novel_id': novel_id
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@parsing_bp.route('/novels/<int:novel_id>/parse/cancel', methods=['POST'])
def cancel_parsing(novel_id):
    """
    Отмена парсинга новеллы
    """
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        if not novel.parsing_task_id:
            return jsonify({
                'success': False,
                'error': 'Парсинг не запущен'
            }), 400

        # Отменяем задачу
        task_id = novel.parsing_task_id
        celery.control.revoke(task_id, terminate=True, signal='SIGTERM')

        # Обновляем статус
        novel.parsing_task_id = None
        novel.status = 'parsing_cancelled'
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Парсинг отменен',
            'task_id': task_id
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@parsing_bp.route('/novels/<int:novel_id>/parse/status', methods=['GET'])
def get_parsing_status(novel_id):
    """
    Получение статуса парсинга
    """
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        if not novel.parsing_task_id:
            return jsonify({
                'success': True,
                'parsing': False,
                'status': novel.status,
                'parsed_chapters': novel.parsed_chapters,
                'total_chapters': novel.total_chapters
            })

        # Получаем статус задачи
        task = celery.AsyncResult(novel.parsing_task_id)

        response = {
            'success': True,
            'parsing': True,
            'task_id': novel.parsing_task_id,
            'state': task.state,
            'status': novel.status,
            'parsed_chapters': novel.parsed_chapters,
            'total_chapters': novel.total_chapters
        }

        # Добавляем информацию о прогрессе
        if task.state == 'PROGRESS':
            info = task.info or {}
            response.update({
                'progress': info.get('progress', 0),
                'current_status': info.get('status', ''),
                'current_chapter': info.get('current_chapter', 0),
                'saved_chapters': info.get('saved_chapters', 0)
            })
        elif task.state == 'SUCCESS':
            result = task.result or {}
            response.update({
                'completed': True,
                'message': result.get('message', 'Парсинг завершен'),
                'saved_chapters': result.get('saved_chapters', 0),
                'total_processed': result.get('total_chapters', 0)
            })
            # Очищаем task_id
            if novel.parsing_task_id == task.id:
                novel.parsing_task_id = None
                db.session.commit()
        elif task.state == 'FAILURE':
            response.update({
                'error': True,
                'error_message': str(task.info)
            })
            # Очищаем task_id
            if novel.parsing_task_id == task.id:
                novel.parsing_task_id = None
                db.session.commit()

        return jsonify(response)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@parsing_bp.route('/tasks/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """
    Получение статуса любой Celery задачи
    """
    try:
        task = celery.AsyncResult(task_id)

        response = {
            'success': True,
            'task_id': task_id,
            'state': task.state,
            'ready': task.ready(),
            'successful': task.successful() if task.ready() else None,
            'failed': task.failed() if task.ready() else None
        }

        if task.state == 'PROGRESS':
            response['info'] = task.info or {}
        elif task.state == 'SUCCESS':
            response['result'] = task.result
        elif task.state == 'FAILURE':
            response['error'] = str(task.info)

        return jsonify(response)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
