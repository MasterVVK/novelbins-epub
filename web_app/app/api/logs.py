"""
API endpoints для работы с логами
"""
from flask import Blueprint, request, jsonify
from app.services.log_service import LogService
from app.models import Task, Novel, Chapter
from app.models.log_entry import LogEntry
from datetime import datetime, timedelta
from sqlalchemy import desc

logs_bp = Blueprint('logs', __name__)


@logs_bp.route('/logs', methods=['GET'])
def get_logs():
    """Получение логов с фильтрацией"""
    try:
        # Параметры запроса
        task_id = request.args.get('task_id', type=int)
        novel_id = request.args.get('novel_id', type=int)
        chapter_id = request.args.get('chapter_id', type=int)
        level = request.args.get('level')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Получаем логи
        logs = LogService.get_logs(
            task_id=task_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            level=level,
            limit=limit,
            offset=offset
        )
        
        # Преобразуем в JSON
        logs_data = [log.to_dict() for log in logs]
        
        return jsonify({
            'success': True,
            'logs': logs_data,
            'count': len(logs_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/logs/recent', methods=['GET'])
def get_recent_logs():
    """Получение недавних логов с фильтрацией"""
    try:
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)
        level = request.args.get('level')
        task_id = request.args.get('task_id', type=int)
        novel_id = request.args.get('novel_id', type=int)

        # Строим SQL запрос с фильтрами
        since = datetime.utcnow() - timedelta(hours=hours)
        query = LogEntry.query.filter(LogEntry.created_at >= since)

        # Применяем фильтры на уровне SQL (ДО лимита)
        if level:
            query = query.filter(LogEntry.level == level)
        if task_id:
            query = query.filter(LogEntry.task_id == task_id)
        if novel_id:
            query = query.filter(LogEntry.novel_id == novel_id)

        # Применяем сортировку и лимит ПОСЛЕ фильтрации
        logs = query.order_by(desc(LogEntry.created_at)).limit(limit).all()
        logs_data = [log.to_dict() for log in logs]

        return jsonify({
            'success': True,
            'logs': logs_data,
            'count': len(logs_data)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/logs/errors', methods=['GET'])
def get_error_logs():
    """Получение только ошибок"""
    try:
        limit = request.args.get('limit', 100, type=int)
        
        logs = LogService.get_error_logs(limit=limit)
        logs_data = [log.to_dict() for log in logs]
        
        return jsonify({
            'success': True,
            'logs': logs_data,
            'count': len(logs_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/logs/task/<int:task_id>', methods=['GET'])
def get_task_logs(task_id):
    """Получение логов конкретной задачи"""
    try:
        limit = request.args.get('limit', 100, type=int)
        
        # Проверяем существование задачи
        task = Task.query.get(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': 'Задача не найдена'
            }), 404
        
        logs = LogService.get_task_logs(task_id, limit=limit)
        logs_data = [log.to_dict() for log in logs]
        
        return jsonify({
            'success': True,
            'task': {
                'id': task.id,
                'type': task.task_type,
                'status': task.status,
                'progress': task.progress
            },
            'logs': logs_data,
            'count': len(logs_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/logs/novel/<int:novel_id>', methods=['GET'])
def get_novel_logs(novel_id):
    """Получение логов конкретной новеллы"""
    try:
        limit = request.args.get('limit', 100, type=int)
        
        # Проверяем существование новеллы
        novel = Novel.query.get(novel_id)
        if not novel:
            return jsonify({
                'success': False,
                'error': 'Новелла не найдена'
            }), 404
        
        logs = LogService.get_novel_logs(novel_id, limit=limit)
        logs_data = [log.to_dict() for log in logs]
        
        return jsonify({
            'success': True,
            'novel': {
                'id': novel.id,
                'title': novel.title,
                'status': novel.status
            },
            'logs': logs_data,
            'count': len(logs_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/logs/stats', methods=['GET'])
def get_log_stats():
    """Получение статистики логов"""
    try:
        stats = LogService.get_log_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/logs/clear', methods=['POST'])
def clear_old_logs():
    """Очистка старых логов"""
    try:
        days = request.json.get('days', 30) if request.is_json else 30
        
        deleted_count = LogService.clear_old_logs(days=days)
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Удалено {deleted_count} старых логов'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 