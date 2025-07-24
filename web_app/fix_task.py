#!/usr/bin/env python3
"""
Быстрое исправление зависшей задачи
"""
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Task

def fix_task(task_id):
    """Исправление конкретной задачи"""
    app = create_app()
    with app.app_context():
        print(f"🔧 ИСПРАВЛЕНИЕ ЗАДАЧИ {task_id}")
        print("=" * 30)
        
        task = Task.query.get(task_id)
        if not task:
            print(f"❌ Задача {task_id} не найдена")
            return False
        
        print(f"📋 Задача: {task.task_type} для новеллы {task.novel_id}")
        print(f"   Статус: {task.status}")
        print(f"   Прогресс: {task.progress}%")
        print(f"   Создана: {task.created_at}")
        
        if task.status == 'running':
            task.status = 'failed'
            task.error_message = 'Задача исправлена вручную'
            db.session.commit()
            print(f"✅ Задача {task_id} исправлена (статус изменен на 'failed')")
            return True
        else:
            print(f"ℹ️ Задача {task_id} не требует исправления")
            return False

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Использование: python fix_task.py <task_id>")
        print("Пример: python fix_task.py 2")
        sys.exit(1)
    
    try:
        task_id = int(sys.argv[1])
        fix_task(task_id)
    except ValueError:
        print("❌ Ошибка: task_id должен быть числом")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1) 