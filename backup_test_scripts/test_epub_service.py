#!/usr/bin/env python3
"""
Тест EPUB сервиса
"""
import sys
import os
from pathlib import Path

# Добавляем путь к web_app
web_app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_app')
sys.path.insert(0, web_app_path)

from app import create_app, db
from app.models import Novel, Chapter, Translation
from app.services.epub_service import EPUBService

def test_epub_service():
    """Тестирование EPUB сервиса"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Тестирование EPUB сервиса...")
        
        # Получаем первую новеллу
        novel = Novel.query.first()
        if not novel:
            print("❌ Нет новелл в базе данных")
            return
        
        print(f"📖 Найдена новелла: {novel.title}")
        
        # Получаем главы с переводами
        chapters = Chapter.query.filter_by(novel_id=novel.id, is_active=True).all()
        print(f"📚 Найдено глав: {len(chapters)}")
        
        # Проверяем переводы
        translated_chapters = []
        for chapter in chapters:
            if chapter.current_translation:
                translated_chapters.append(chapter)
                print(f"   Глава {chapter.chapter_number}: {chapter.current_translation.translated_title}")
        
        if not translated_chapters:
            print("❌ Нет переведенных глав")
            return
        
        print(f"✅ Найдено переведенных глав: {len(translated_chapters)}")
        
        # Тестируем EPUB сервис
        epub_service = EPUBService(app)
        
        try:
            # Получаем главы для EPUB
            epub_chapters = epub_service.get_edited_chapters_from_db(novel.id)
            print(f"📖 Получено глав для EPUB: {len(epub_chapters)}")
            
            if epub_chapters:
                # Создаем EPUB
                epub_path = epub_service.create_epub(novel.id, epub_chapters)
                print(f"✅ EPUB создан: {epub_path}")
                
                # Проверяем размер файла
                epub_file = Path(epub_path)
                if epub_file.exists():
                    size_kb = epub_file.stat().st_size / 1024
                    print(f"📊 Размер файла: {size_kb:.1f} KB")
                else:
                    print("❌ Файл не найден")
            else:
                print("❌ Нет глав для создания EPUB")
                
        except Exception as e:
            print(f"❌ Ошибка при создании EPUB: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_epub_service() 