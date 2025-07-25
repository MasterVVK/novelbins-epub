#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter, Translation

app = create_app()

with app.app_context():
    print("🧪 Простой тест EditorService...")
    
    # Получаем главу
    chapter = Chapter.query.filter_by(
        novel_id=2,
        chapter_number=1,
        is_active=True
    ).first()
    
    if not chapter:
        print("❌ Глава не найдена")
        exit(1)
    
    print(f"📖 Найдена глава: {chapter.original_title}")
    
    # Получаем последний перевод
    latest_translation = Translation.query.filter_by(
        chapter_id=chapter.id
    ).order_by(Translation.created_at.desc()).first()
    
    if not latest_translation:
        print("❌ Перевод не найден")
        exit(1)
    
    print(f"✅ Найден перевод длиной {len(latest_translation.translated_text)} символов")
    print(f"📝 Начало текста: {latest_translation.translated_text[:100]}...")
    
    # Тестируем EditorService
    try:
        from app.services.translator_service import TranslatorService
        from app.services.editor_service import EditorService
        
        print("🔧 Инициализируем TranslatorService...")
        translator_service = TranslatorService()
        print("✅ TranslatorService инициализирован")
        
        print("🔧 Инициализируем EditorService...")
        editor_service = EditorService(translator_service)
        print("✅ EditorService инициализирован")
        
        print("📝 Тестируем edit_chapter...")
        success = editor_service.edit_chapter(chapter)
        
        if success:
            print("✅ Редактура завершена успешно!")
        else:
            print("❌ Редактура завершена с ошибкой")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc() 