"""
API endpoints для управления сопоставлением с оригиналом через Celery
"""
from flask import Blueprint, request, jsonify
from app.models import Novel
from app import db, celery
from app.celery_tasks import align_novel_chapters_task

alignment_bp = Blueprint('alignment', __name__)


@alignment_bp.route('/novels/<int:novel_id>/alignment/cancel', methods=['POST'])
def cancel_alignment(novel_id):
    """
    Отмена сопоставления новеллы
    """
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        if not novel.alignment_task_id:
            return jsonify({
                'success': False,
                'error': 'Сопоставление не запущено'
            }), 400

        # Отменяем задачу НАПРЯМУЮ через celery.control.revoke (синхронно)
        task_id = novel.alignment_task_id
        celery.control.revoke(task_id, terminate=True, signal='SIGTERM')

        # Обновляем статус немедленно
        novel.status = 'alignment_cancelled'
        novel.alignment_task_id = None
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Сопоставление отменено',
            'task_id': task_id
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@alignment_bp.route('/api/novels/<int:novel_id>/alignment-status')
def get_alignment_status(novel_id):
    """
    Получить статус сопоставления новеллы
    """
    try:
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404

        if not novel.alignment_task_id:
            return jsonify({
                'is_running': False,
                'progress': novel.alignment_progress_percentage,
                'aligned_count': novel.aligned_chapters or 0
            })

        from celery.result import AsyncResult
        task = AsyncResult(novel.alignment_task_id, app=celery)

        if task.state == 'PROGRESS':
            meta = task.info or {}
            return jsonify({
                'is_running': True,
                'state': task.state,
                'progress': meta.get('progress', 0),
                'aligned_count': meta.get('success_count', novel.aligned_chapters or 0),
                'status': meta.get('status', 'Сопоставление...')
            })
        elif task.state in ['PENDING', 'STARTED']:
            return jsonify({
                'is_running': True,
                'state': task.state,
                'progress': 0,
                'aligned_count': novel.aligned_chapters or 0,
                'status': 'Запуск...'
            })
        else:
            return jsonify({
                'is_running': False,
                'state': task.state,
                'progress': novel.alignment_progress_percentage,
                'aligned_count': novel.aligned_chapters or 0
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
