#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Task

app = create_app()

def cleanup_hanging_tasks():
    """Очистка зависших задач редактуры"""
    print("🧹 ОЧИСТКА ЗАВИСШИХ ЗАДАЧ")
    print("=" * 40)
    
    with app.app_context():
        # Находим зависшие задачи редактуры
        hanging_tasks = Task.query.filter_by(
            novel_id=2,
            task_type='editing',
            status='running'
        ).all()
        
        print(f"📊 Найдено зависших задач: {len(hanging_tasks)}")
        
        for task in hanging_tasks:
            print(f"  Задача {task.id}: {task.status} (создана: {task.created_at})")
            task.status = 'failed'
            task.error_message = 'Задача зависла и была очищена'
            db.session.add(task)
        
        if hanging_tasks:
            db.session.commit()
            print(f"✅ Очищено {len(hanging_tasks)} зависших задач")
        else:
            print("✅ Зависших задач не найдено")

if __name__ == "__main__":
    cleanup_hanging_tasks() 