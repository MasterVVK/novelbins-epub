#!/usr/bin/env python3
"""
Создание тестовой завершенной задачи EPUB
"""
import sys
import os
from pathlib import Path

# Добавляем путь к web_app
web_app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_app')
sys.path.insert(0, web_app_path)

from app import create_app, db
from app.models import Novel, Task

def create_test_epub_task():
    """Создание тестовой завершенной задачи EPUB"""
    app = create_app()
    
    with app.app_context():
        print("🔧 Создание тестовой задачи EPUB...")
        
        # Получаем первую новеллу
        novel = Novel.query.first()
        if not novel:
            print("❌ Нет новелл в базе данных")
            return
        
        print(f"📖 Найдена новелла: {novel.title} (ID: {novel.id})")
        
        # Создаем завершенную задачу EPUB
        task = Task(
            novel_id=novel.id,
            task_type='generate_epub',
            status='completed',
            priority=2,
            result={
                'epub_path': '/home/user/novelbins-epub/web_app/instance/epub_output/Покрывая_Небеса_1-3_edited_20250725_100629.epub'
            }
        )
        
        db.session.add(task)
        db.session.commit()
        
        print(f"✅ Создана завершенная задача EPUB: {task.id}")
        print(f"📁 Путь к файлу: {task.result['epub_path']}")
        
        # Проверяем, что файл существует
        epub_file = Path(task.result['epub_path'])
        if epub_file.exists():
            size_kb = epub_file.stat().st_size / 1024
            print(f"✅ Файл существует, размер: {size_kb:.1f} KB")
        else:
            print(f"⚠️ Файл не найден: {epub_file}")
        
        print(f"\n🔗 URL для тестирования:")
        print(f"   Детальная страница: http://localhost:5001/novels/{novel.id}")
        print(f"   Скачивание EPUB: http://localhost:5001/novels/{novel.id}/epub/download")

if __name__ == "__main__":
    create_test_epub_task() 