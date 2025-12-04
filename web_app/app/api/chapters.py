"""API endpoints для работы с главами"""
from flask import Blueprint, request, jsonify
from app.models import Chapter, Novel
from app import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

chapters_bp = Blueprint('chapters_api', __name__, url_prefix='/api/chapters')


@chapters_bp.route('/<int:chapter_id>/status', methods=['POST'])
def update_chapter_status(chapter_id):
    """API для обновления статуса главы"""
    try:
        chapter = Chapter.query.get_or_404(chapter_id)
        data = request.json
        new_status = data.get('status')

        # Валидация статуса
        valid_statuses = ['pending', 'parsed', 'translated', 'edited', 'aligned', 'error']
        if new_status not in valid_statuses:
            return jsonify({
                'success': False,
                'error': f'Недопустимый статус. Допустимые значения: {", ".join(valid_statuses)}'
            }), 400

        old_status = chapter.status
        chapter.status = new_status
        chapter.updated_at = datetime.utcnow()
        db.session.commit()

        # Обновляем статистику новеллы
        novel = Novel.query.get(chapter.novel_id)
        if novel:
            novel.update_stats()

        logger.info(f"Статус главы {chapter_id} изменен с '{old_status}' на '{new_status}'")

        return jsonify({
            'success': True,
            'chapter_id': chapter_id,
            'old_status': old_status,
            'new_status': new_status,
            'message': f'Статус главы {chapter.chapter_number} изменен'
        })

    except Exception as e:
        logger.error(f"Ошибка обновления статуса главы {chapter_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
