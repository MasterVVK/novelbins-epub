#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter, Translation

app = create_app()

with app.app_context():
    print("🔍 Сравниваем исходный перевод и редактуру...")
    
    # Получаем отредактированную главу
    chapter = Chapter.query.filter_by(
        novel_id=2,
        chapter_number=1,
        is_active=True
    ).first()
    
    if not chapter:
        print("❌ Глава не найдена")
        exit(1)
    
    print(f"📖 Глава: {chapter.original_title}")
    print(f"📊 Статус: {chapter.status}")
    
    # Получаем исходный перевод
    original_translation = chapter.current_translation
    edited_translation = chapter.edited_translation
    
    print(f"\n📋 Сравнение переводов:")
    print(f"  Исходный перевод: {'Есть' if original_translation else 'Нет'}")
    print(f"  Редактура: {'Есть' if edited_translation else 'Нет'}")
    
    if original_translation and edited_translation:
        print(f"\n📊 Статистика:")
        print(f"  Исходный перевод:")
        print(f"    Тип: {original_translation.translation_type}")
        print(f"    API: {original_translation.api_used}")
        print(f"    Длина: {len(original_translation.translated_text)} символов")
        print(f"    Начало: {original_translation.translated_text[:100]}...")
        
        print(f"\n  Редактура:")
        print(f"    Тип: {edited_translation.translation_type}")
        print(f"    API: {edited_translation.api_used}")
        print(f"    Длина: {len(edited_translation.translated_text)} символов")
        print(f"    Начало: {edited_translation.translated_text[:100]}...")
        
        # Проверяем, что тексты действительно разные
        if original_translation.translated_text != edited_translation.translated_text:
            print(f"\n✅ Тексты РАЗНЫЕ - редактура работает!")
            print(f"  Разница в длине: {len(original_translation.translated_text) - len(edited_translation.translated_text)} символов")
        else:
            print(f"\n❌ Тексты ОДИНАКОВЫЕ - проблема!")
    else:
        print(f"\n❌ Не удалось получить оба перевода") 