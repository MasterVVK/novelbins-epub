#!/usr/bin/env python3

import sys
import os
import time
import requests
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter, Translation, Task

app = create_app()

def test_editing_realtime():
    """Тестирование редактуры в реальном времени"""
    print("🔍 ТЕСТИРОВАНИЕ РЕДАКТУРЫ В РЕАЛЬНОМ ВРЕМЕНИ")
    print("=" * 60)
    
    base_url = "http://192.168.0.58:5001"
    novel_id = 2
    
    with app.app_context():
        # Проверяем начальное состояние
        print("\n📊 НАЧАЛЬНОЕ СОСТОЯНИЕ:")
        initial_tasks = Task.query.filter_by(novel_id=novel_id, task_type='editing').count()
        print(f"  Задач редактуры: {initial_tasks}")
        
        ready_chapters = Chapter.query.filter_by(
            novel_id=novel_id,
            status='translated',
            is_active=True
        ).count()
        print(f"  Глав готовых к редактуре: {ready_chapters}")
        
        # Отправляем запрос на редактуру
        print(f"\n🚀 ОТПРАВЛЯЕМ ЗАПРОС НА РЕДАКТУРУ...")
        editing_url = f"{base_url}/novels/{novel_id}/start-editing"
        
        try:
            response = requests.post(editing_url, timeout=10)
            print(f"  Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                print("  ✅ Запрос успешен")
            else:
                print(f"  ❌ Ошибка: {response.status_code}")
                return
                
        except Exception as e:
            print(f"  ❌ Ошибка запроса: {e}")
            return
        
        # Мониторим изменения в реальном времени
        print(f"\n📈 МОНИТОРИНГ ИЗМЕНЕНИЙ:")
        for i in range(10):  # 10 проверок по 2 секунды
            time.sleep(2)
            
            with app.app_context():
                # Проверяем задачи
                tasks = Task.query.filter_by(novel_id=novel_id, task_type='editing').all()
                print(f"  [{i+1:2d}] Задач редактуры: {len(tasks)}")
                
                for task in tasks:
                    print(f"      Задача {task.id}: {task.status} (прогресс: {task.progress})")
                    if task.error_message:
                        print(f"        ❌ Ошибка: {task.error_message}")
                
                # Проверяем главы
                edited_chapters = Chapter.query.filter_by(
                    novel_id=novel_id,
                    status='edited',
                    is_active=True
                ).count()
                print(f"      Отредактированных глав: {edited_chapters}")
        
        # Финальная проверка
        print(f"\n📊 ФИНАЛЬНОЕ СОСТОЯНИЕ:")
        final_tasks = Task.query.filter_by(novel_id=novel_id, task_type='editing').all()
        print(f"  Задач редактуры: {len(final_tasks)}")
        
        for task in final_tasks:
            print(f"    Задача {task.id}: {task.status}")
            print(f"      Создана: {task.created_at}")
            print(f"      Начата: {task.started_at}")
            print(f"      Завершена: {task.completed_at}")
            if task.error_message:
                print(f"      ❌ Ошибка: {task.error_message}")
            if task.result:
                print(f"      📄 Результат: {task.result}")
        
        # Проверяем главы
        chapters = Chapter.query.filter_by(novel_id=novel_id, is_active=True).all()
        print(f"\n📋 СТАТУСЫ ГЛАВ:")
        for chapter in chapters:
            print(f"  Глава {chapter.chapter_number}: {chapter.status}")

if __name__ == "__main__":
    test_editing_realtime() 