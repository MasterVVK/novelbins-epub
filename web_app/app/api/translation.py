"""
API endpoints для управления переводом через Celery
"""
from flask import Blueprint, jsonify
from app.models import Novel
from app import db, celery

translation_bp = Blueprint('translation', __name__)


@translation_bp.route('/novels/<int:novel_id>/translate/cancel', methods=['POST'])
def cancel_translation(novel_id):
    """
    Отмена перевода новеллы
    """
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        if not novel.translation_task_id:
            return jsonify({
                'success': False,
                'error': 'Перевод не запущен'
            }), 400

        # Отменяем задачу через celery.control.revoke
        task_id = novel.translation_task_id
        celery.control.revoke(task_id, terminate=True, signal='SIGTERM')

        # Обновляем статус немедленно
        novel.status = 'translation_cancelled'
        novel.translation_task_id = None
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Перевод отменён',
            'task_id': task_id
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
