#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Task

app = create_app()

def check_tasks():
    """Проверка задач редактуры"""
    with app.app_context():
        tasks = Task.query.filter_by(
            novel_id=2,
            task_type='editing'
        ).order_by(Task.created_at.desc()).limit(5).all()
        
        print(f"📊 Найдено задач редактуры: {len(tasks)}")
        for task in tasks:
            print(f"  Задача {task.id}: {task.status} (создана: {task.created_at})")
            if task.error_message:
                print(f"    ❌ Ошибка: {task.error_message}")

if __name__ == "__main__":
    check_tasks() 