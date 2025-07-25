#!/usr/bin/env python3
"""
Тест веб-интерфейса EPUB
"""
import sys
import os
from pathlib import Path

# Добавляем путь к web_app
web_app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_app')
sys.path.insert(0, web_app_path)

from app import create_app, db
from app.models import Novel, Chapter, Translation, Task

def test_epub_web_interface():
    """Тестирование веб-интерфейса EPUB"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Тестирование веб-интерфейса EPUB...")
        
        # Получаем первую новеллу
        novel = Novel.query.first()
        if not novel:
            print("❌ Нет новелл в базе данных")
            return
        
        print(f"📖 Найдена новелла: {novel.title} (ID: {novel.id})")
        
        # Получаем задачи для новеллы
        tasks = Task.query.filter_by(novel_id=novel.id).all()
        print(f"📋 Найдено задач: {len(tasks)}")
        
        for task in tasks:
            print(f"   - {task.task_type}: {task.status} (создана: {task.created_at})")
        
        # Проверяем задачи EPUB
        epub_tasks = [t for t in tasks if t.task_type == 'generate_epub']
        print(f"📚 Задач EPUB: {len(epub_tasks)}")
        
        for task in epub_tasks:
            print(f"   - EPUB задача {task.id}: {task.status}")
            if task.result:
                print(f"     Результат: {task.result}")
            if task.error_message:
                print(f"     Ошибка: {task.error_message}")
        
        # Проверяем главы
        chapters = Chapter.query.filter_by(novel_id=novel.id, is_active=True).all()
        print(f"📖 Глав: {len(chapters)}")
        
        translated_count = 0
        for chapter in chapters:
            if chapter.current_translation:
                translated_count += 1
                print(f"   - Глава {chapter.chapter_number}: {chapter.status}")
        
        print(f"✅ Переведенных глав: {translated_count}")
        
        # Проверяем, есть ли готовый EPUB для скачивания
        completed_epub_task = Task.query.filter_by(
            novel_id=novel.id,
            task_type='generate_epub',
            status='completed'
        ).order_by(Task.updated_at.desc()).first()
        
        if completed_epub_task and completed_epub_task.result:
            epub_path = completed_epub_task.result.get('epub_path')
            if epub_path:
                epub_file = Path(epub_path)
                if epub_file.exists():
                    size_kb = epub_file.stat().st_size / 1024
                    print(f"✅ Готовый EPUB найден: {epub_path}")
                    print(f"📊 Размер: {size_kb:.1f} KB")
                else:
                    print(f"❌ EPUB файл не найден: {epub_path}")
            else:
                print("❌ Путь к EPUB не указан в результате")
        else:
            print("ℹ️ Готовый EPUB не найден")
        
        print("\n🔗 URL для тестирования:")
        print(f"   Детальная страница новеллы: http://localhost:5001/novels/{novel.id}")
        print(f"   Скачивание EPUB: http://localhost:5001/novels/{novel.id}/epub/download")

if __name__ == "__main__":
    test_epub_web_interface() 