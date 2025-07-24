#!/usr/bin/env python3
"""
Скрипт для удаления всей истории задач
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.task import Task

def clear_all_tasks():
    """Удаляет все задачи из базы данных"""
    app = create_app()
    
    with app.app_context():
        try:
            # Получаем количество задач
            task_count = Task.query.count()
            print(f"🔍 Найдено задач в базе данных: {task_count}")
            
            if task_count == 0:
                print("✅ История задач уже пуста")
                return
            
            # Удаляем все задачи
            deleted_count = Task.query.delete()
            db.session.commit()
            
            print(f"✅ Удалено задач: {deleted_count}")
            print("✅ История задач полностью очищена")
            
        except Exception as e:
            print(f"❌ Ошибка при удалении задач: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    print("🧹 Очистка истории задач...")
    clear_all_tasks()
    print("✅ Готово!") 