#!/usr/bin/env python3

import sys
import os
import time
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Task

app = create_app()

def monitor_task():
    """Мониторинг последней задачи редактуры"""
    print("📊 МОНИТОРИНГ ЗАДАЧИ РЕДАКТУРЫ")
    print("=" * 40)
    
    with app.app_context():
        for i in range(10):
            task = Task.query.filter_by(
                novel_id=2,
                task_type='editing'
            ).order_by(Task.created_at.desc()).first()
            
            if task:
                print(f"[{i+1:2d}] Задача {task.id}: {task.status} (прогресс: {task.progress})")
                if task.error_message:
                    print(f"     ❌ Ошибка: {task.error_message}")
                if task.result:
                    print(f"     📄 Результат: {task.result}")
            else:
                print(f"[{i+1:2d}] Задача не найдена")
            
            time.sleep(3)

if __name__ == "__main__":
    monitor_task() 