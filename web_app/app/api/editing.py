"""
API endpoints для управления редактурой через Celery
"""
from flask import Blueprint, request, jsonify
from app.models import Novel
from app import db, celery
from app.celery_tasks import edit_novel_chapters_task, cancel_editing_task

editing_bp = Blueprint('editing', __name__)


@editing_bp.route('/novels/<int:novel_id>/edit/cancel', methods=['POST'])
def cancel_editing(novel_id):
    """
    Отмена редактуры новеллы
    """
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        if not novel.editing_task_id:
            return jsonify({
                'success': False,
                'error': 'Редактура не запущена'
            }), 400

        # Отменяем задачу НАПРЯМУЮ через celery.control.revoke (синхронно)
        task_id = novel.editing_task_id
        celery.control.revoke(task_id, terminate=True, signal='SIGTERM')

        # Обновляем статус немедленно
        novel.status = 'editing_cancelled'
        novel.editing_task_id = None
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Редактура отменена',
            'task_id': task_id
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
