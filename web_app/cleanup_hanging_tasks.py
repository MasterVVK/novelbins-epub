#!/usr/bin/env python3
"""
Скрипт для очистки зависших задач
"""
import sys
import os
from datetime import datetime, timedelta

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Task

def cleanup_hanging_tasks():
    """Очистка зависших задач"""
    app = create_app()
    with app.app_context():
        print("🧹 ОЧИСТКА ЗАВИСШИХ ЗАДАЧ")
        print("=" * 40)
        
        # Находим зависшие задачи (running более 1 часа)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        hanging_tasks = Task.query.filter(
            Task.status == 'running',
            Task.created_at < cutoff_time
        ).all()
        
        print(f"📋 Найдено зависших задач: {len(hanging_tasks)}")
        
        if not hanging_tasks:
            print("✅ Нет зависших задач для очистки")
            return
        
        # Показываем зависшие задачи
        print("\n📊 ЗАВИСШИЕ ЗАДАЧИ:")
        for task in hanging_tasks:
            print(f"   ID: {task.id}, тип: {task.task_type}, новелла: {task.novel_id}")
            print(f"      Создана: {task.created_at}")
            print(f"      Прогресс: {task.progress}%")
        
        # Очищаем зависшие задачи
        cleaned_count = 0
        for task in hanging_tasks:
            try:
                task.status = 'failed'
                task.error_message = 'Задача зависла и была автоматически завершена'
                print(f"✅ Задача {task.id} помечена как failed")
                cleaned_count += 1
            except Exception as e:
                print(f"❌ Ошибка при очистке задачи {task.id}: {e}")
        
        # Сохраняем изменения
        try:
            db.session.commit()
            print(f"\n📊 РЕЗУЛЬТАТ:")
            print(f"   Очищено задач: {cleaned_count}")
        except Exception as e:
            print(f"❌ Ошибка при сохранении: {e}")
            db.session.rollback()

def check_task_status():
    """Проверка статуса задач"""
    app = create_app()
    with app.app_context():
        print("\n🔍 ПРОВЕРКА СТАТУСА ЗАДАЧ")
        print("=" * 30)
        
        # Все задачи
        all_tasks = Task.query.order_by(Task.created_at.desc()).limit(10).all()
        print(f"📋 Последние 10 задач:")
        
        for task in all_tasks:
            print(f"   ID: {task.id}, тип: {task.task_type}, статус: {task.status}")
            print(f"      Новелла: {task.novel_id}, прогресс: {task.progress}%")
            print(f"      Создана: {task.created_at}")
            if task.status == 'running':
                age = datetime.utcnow() - task.created_at
                print(f"      Возраст: {age}")
            print()

def fix_specific_task(task_id):
    """Исправление конкретной задачи"""
    app = create_app()
    with app.app_context():
        print(f"\n🔧 ИСПРАВЛЕНИЕ ЗАДАЧИ {task_id}")
        print("=" * 30)
        
        task = Task.query.get(task_id)
        if not task:
            print(f"❌ Задача {task_id} не найдена")
            return
        
        print(f"📋 Задача: {task.task_type} для новеллы {task.novel_id}")
        print(f"   Статус: {task.status}")
        print(f"   Прогресс: {task.progress}%")
        print(f"   Создана: {task.created_at}")
        
        if task.status == 'running':
            task.status = 'failed'
            task.error_message = 'Задача исправлена вручную'
            db.session.commit()
            print(f"✅ Задача {task_id} исправлена")
        else:
            print(f"ℹ️ Задача {task_id} не требует исправления")

if __name__ == '__main__':
    print("🚀 ЗАПУСК ОЧИСТКИ ЗАВИСШИХ ЗАДАЧ")
    print("=" * 50)
    
    # Проверяем статус
    check_task_status()
    
    # Очищаем зависшие задачи
    cleanup_hanging_tasks()
    
    # Исправляем конкретную задачу (ID=2)
    fix_specific_task(2)
    
    # Проверяем результат
    check_task_status()
    
    print("\n✅ ОЧИСТКА ЗАВЕРШЕНА") 