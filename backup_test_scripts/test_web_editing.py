#!/usr/bin/env python3

import requests
import time
import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter, Translation, Task

app = create_app()

def test_web_editing():
    """Тестирование редактуры через веб-интерфейс"""
    print("🌐 ТЕСТИРОВАНИЕ РЕДАКТУРЫ ЧЕРЕЗ ВЕБ-ИНТЕРФЕЙС")
    print("=" * 60)
    
    base_url = "http://192.168.0.58:5001"
    novel_id = 2
    
    # 1. Проверяем доступность веб-приложения
    print("\n🔍 1. ПРОВЕРКА ДОСТУПНОСТИ ВЕБ-ПРИЛОЖЕНИЯ")
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        if response.status_code == 200:
            print("✅ Веб-приложение доступно")
        else:
            print(f"❌ Ошибка доступа: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return
    
    # 2. Проверяем страницу новеллы
    print(f"\n📖 2. ПРОВЕРКА СТРАНИЦЫ НОВЕЛЛЫ")
    try:
        response = requests.get(f"{base_url}/novels/{novel_id}", timeout=10)
        if response.status_code == 200:
            print("✅ Страница новеллы доступна")
            if "Редактура" in response.text:
                print("✅ Кнопка 'Редактура' найдена на странице")
            else:
                print("❌ Кнопка 'Редактура' не найдена")
        else:
            print(f"❌ Ошибка страницы новеллы: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Ошибка загрузки страницы: {e}")
        return
    
    # 3. Проверяем начальное состояние
    print(f"\n📊 3. НАЧАЛЬНОЕ СОСТОЯНИЕ")
    with app.app_context():
        novel = Novel.query.get(novel_id)
        if novel:
            print(f"📖 Новелла: {novel.title}")
            print(f"📈 Отредактировано глав: {novel.edited_chapters}")
        
        # Проверяем главы готовые к редактуре
        ready_chapters = Chapter.query.filter_by(
            novel_id=novel_id,
            status='translated',
            is_active=True
        ).count()
        print(f"📝 Глав готовых к редактуре: {ready_chapters}")
        
        # Проверяем активные задачи
        active_tasks = Task.query.filter_by(
            novel_id=novel_id,
            task_type='editing',
            status='running'
        ).count()
        print(f"🎯 Активных задач редактуры: {active_tasks}")
    
    # 4. Отправляем запрос на редактуру
    print(f"\n🚀 4. ЗАПУСК РЕДАКТУРЫ ЧЕРЕЗ ВЕБ-ИНТЕРФЕЙС")
    editing_url = f"{base_url}/novels/{novel_id}/start-editing"
    
    try:
        print(f"📤 Отправляем POST запрос: {editing_url}")
        response = requests.post(editing_url, timeout=30)
        print(f"📥 Получен ответ: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Запрос на редактуру успешен")
            print(f"📄 Размер ответа: {len(response.content)} байт")
            
            # Проверяем редирект
            if "novels/2" in response.url:
                print("✅ Редирект на страницу новеллы выполнен")
            else:
                print(f"⚠️ Неожиданный редирект: {response.url}")
        else:
            print(f"❌ Ошибка запроса: {response.status_code}")
            print(f"📄 Ответ: {response.text[:200]}...")
            return
            
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return
    
    # 5. Мониторим изменения
    print(f"\n📈 5. МОНИТОРИНГ ИЗМЕНЕНИЙ")
    for i in range(10):  # 10 проверок по 10 секунд
        time.sleep(10)
        
        with app.app_context():
            # Проверяем задачи
            tasks = Task.query.filter_by(
                novel_id=novel_id,
                task_type='editing'
            ).order_by(Task.created_at.desc()).limit(3).all()
            
            print(f"\n  [{i+1:2d}] Проверка через {10*(i+1)} сек:")
            print(f"      Задач редактуры: {len(tasks)}")
            
            for task in tasks:
                print(f"        Задача {task.id}: {task.status} (прогресс: {task.progress})")
                if task.error_message:
                    print(f"          ❌ Ошибка: {task.error_message}")
            
            # Проверяем отредактированные главы
            edited_chapters = Chapter.query.filter_by(
                novel_id=novel_id,
                status='edited',
                is_active=True
            ).count()
            print(f"      Отредактированных глав: {edited_chapters}")
            
            # Если все главы отредактированы, завершаем
            if edited_chapters >= 3:
                print(f"      ✅ Все главы отредактированы!")
                break
    
    # 6. Финальная проверка
    print(f"\n📊 6. ФИНАЛЬНОЕ СОСТОЯНИЕ")
    with app.app_context():
        novel = Novel.query.get(novel_id)
        if novel:
            print(f"📖 Новелла: {novel.title}")
            print(f"📈 Отредактировано глав: {novel.edited_chapters}")
        
        chapters = Chapter.query.filter_by(
            novel_id=novel_id,
            is_active=True
        ).order_by(Chapter.chapter_number).all()
        
        print(f"\n📋 СТАТУСЫ ГЛАВ:")
        for chapter in chapters:
            print(f"  Глава {chapter.chapter_number}: {chapter.status}")
            if chapter.status == 'edited':
                edited_translations = [t for t in chapter.translations if t.translation_type == 'edited']
                if edited_translations:
                    print(f"    📄 Отредактированных переводов: {len(edited_translations)}")
        
        # Проверяем завершенные задачи
        completed_tasks = Task.query.filter_by(
            novel_id=novel_id,
            task_type='editing',
            status='completed'
        ).count()
        print(f"\n🎯 Завершенных задач редактуры: {completed_tasks}")
    
    print(f"\n✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")

if __name__ == "__main__":
    test_web_editing() 