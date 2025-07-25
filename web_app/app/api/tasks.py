"""
API endpoints для работы с задачами
"""
from flask import Blueprint, request, jsonify
from app.models import Task, Novel
from app import db

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """Получение списка задач"""
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        tasks = Task.query.order_by(Task.created_at.desc()).offset(offset).limit(limit).all()
        
        tasks_data = []
        for task in tasks:
            if task and hasattr(task, 'id') and task.id is not None:
                task_data = {
                    'id': task.id,
                    'novel_id': task.novel_id,
                    'chapter_id': task.chapter_id,
                    'task_type': task.task_type or 'unknown',
                    'status': task.status or 'unknown',
                    'progress': task.progress or 0,
                    'current_step': task.current_step,
                    'total_steps': task.total_steps or 1,
                    'error_message': task.error_message,
                    'started_at': task.started_at.isoformat() if task.started_at else None,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'duration': task.duration,
                    'priority': task.priority or 5,
                    'created_at': task.created_at.isoformat() if task.created_at else None,
                    'updated_at': task.updated_at.isoformat() if task.updated_at else None
                }
                
                # Добавляем информацию о новелле
                if task.novel and hasattr(task.novel, 'id') and task.novel.id is not None:
                    task_data['novel'] = {
                        'id': task.novel.id,
                        'title': task.novel.title or 'Без названия'
                    }
                
                tasks_data.append(task_data)
        
        return jsonify({
            'success': True,
            'tasks': tasks_data or [],
            'count': len(tasks_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 