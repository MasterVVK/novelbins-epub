#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter, Translation

app = create_app()

with app.app_context():
    print("🔍 Тестируем отображение главы с редактурой...")
    
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
    
    # Проверяем переводы
    print(f"\n📋 Всего переводов: {len(chapter.translations)}")
    for i, trans in enumerate(chapter.translations):
        print(f"  Перевод {i+1}: {trans.translation_type} ({trans.api_used})")
        print(f"    Длина: {len(trans.translated_text)} символов")
        if hasattr(trans, 'metadata') and trans.metadata:
            print(f"    Метаданные: {str(trans.metadata)[:100]}...")
    
    # Проверяем свойства
    print(f"\n🔍 Свойства главы:")
    print(f"  current_translation: {'Есть' if chapter.current_translation else 'Нет'}")
    print(f"  edited_translation: {'Есть' if chapter.edited_translation else 'Нет'}")
    print(f"  is_translated: {chapter.is_translated}")
    print(f"  is_edited: {chapter.is_edited}")
    
    if chapter.edited_translation:
        print(f"\n✅ Отредактированная версия найдена:")
        print(f"  Тип: {chapter.edited_translation.translation_type}")
        print(f"  API: {chapter.edited_translation.api_used}")
        print(f"  Длина: {len(chapter.edited_translation.translated_text)} символов")
        print(f"  Начало текста: {chapter.edited_translation.translated_text[:100]}...")
        
        if chapter.edited_translation.metadata:
            print(f"  Метаданные: {chapter.edited_translation.metadata}")
    else:
        print("\n❌ Отредактированная версия не найдена") 