#!/usr/bin/env python3
"""
Тестовый скрипт для проверки парсинга
"""
from app import create_app, db
from app.models import Novel, Chapter
from app.services.parser_service import WebParserService

def test_parser():
    app = create_app()
    with app.app_context():
        print("🧪 ТЕСТ ПАРСЕРА")
        print("=" * 40)
        
        # Получаем первую новеллу
        novel = Novel.query.first()
        if not novel:
            print("❌ Новеллы не найдены")
            return
        
        print(f"📖 Тестируем новеллу: {novel.title}")
        print(f"🔗 URL: {novel.source_url}")
        print(f"📊 Глав в БД: {Chapter.query.filter_by(novel_id=novel.id).count()}")
        
        # Создаем парсер
        parser = WebParserService()
        
        # Тестируем парсинг глав
        print("\n🔍 Парсинг списка глав...")
        chapters_data = parser.parse_novel_chapters(novel)
        
        if not chapters_data:
            print("❌ Не удалось получить список глав")
            return
        
        print(f"✅ Найдено глав: {len(chapters_data)}")
        
        # Показываем первые 3 главы
        for i, chapter in enumerate(chapters_data[:3]):
            print(f"  {i+1}. Глава {chapter['number']}: {chapter['title']}")
        
        # Тестируем парсинг содержимого первой главы
        if chapters_data:
            first_chapter = chapters_data[0]
            print(f"\n📖 Тестируем парсинг главы {first_chapter['number']}...")
            
            content = parser.parse_chapter_content(first_chapter['url'], first_chapter['number'])
            if content:
                print(f"✅ Контент загружен: {len(content)} символов")
                print(f"📝 Начало: {content[:100]}...")
            else:
                print("❌ Не удалось загрузить контент")

if __name__ == "__main__":
    test_parser() 