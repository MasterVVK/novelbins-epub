#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправления парсера после удаления is_active
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Novel, Chapter
from app.services.parser_service import WebParserService

def test_parser_fix():
    """Тест исправления парсера"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Тест исправления парсера после удаления is_active...")
        
        # Проверяем, что модель Chapter не имеет поле is_active
        chapter_columns = [column.name for column in Chapter.__table__.columns]
        print(f"📋 Поля модели Chapter: {chapter_columns}")
        
        if 'is_active' in chapter_columns:
            print("❌ Поле is_active все еще существует в модели Chapter")
            return False
        else:
            print("✅ Поле is_active удалено из модели Chapter")
        
        # Проверяем, что ParserService импортируется
        try:
            parser = WebParserService()
            print("✅ WebParserService создается без ошибок")
        except Exception as e:
            print(f"❌ Ошибка при создании WebParserService: {e}")
            return False
        
        # Проверяем, что можно получить главы без is_active
        try:
            novels = Novel.query.filter_by(is_active=True).limit(1).all()
            if novels:
                novel = novels[0]
                chapters = Chapter.query.filter_by(novel_id=novel.id).all()
                print(f"✅ Успешно получено {len(chapters)} глав для новеллы '{novel.title}'")
            else:
                print("ℹ️ Нет активных новелл для тестирования")
        except Exception as e:
            print(f"❌ Ошибка при получении глав: {e}")
            return False
        
        print("\n✅ Тест пройден: парсер исправлен после удаления is_active")
        return True

if __name__ == "__main__":
    test_parser_fix() 