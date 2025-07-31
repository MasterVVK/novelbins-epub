#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter

app = create_app()

with app.app_context():
    print("🔍 Проверяем переведенный текст глав...")
    
    # Получаем главы
    chapters = Chapter.query.filter_by(
        novel_id=2,
        status='translated',
        is_active=True
    ).order_by(Chapter.chapter_number).all()
    
    for ch in chapters:
        print(f"\n📖 Глава {ch.chapter_number}: {ch.original_title}")
        print(f"   Статус: {ch.status}")
        print(f"   Есть original_text: {'Да' if ch.original_text else 'Нет'}")
        print(f"   Длина original_text: {len(ch.original_text) if ch.original_text else 0}")
        
        # Проверяем, есть ли переведенный текст в модели Translation
        from app.models import Translation
        translations = Translation.query.filter_by(chapter_id=ch.id).all()
        print(f"   Переводов в базе: {len(translations)}")
        
        for i, trans in enumerate(translations):
            print(f"     Перевод {i+1}: {trans.translation_type} ({trans.api_used})")
            print(f"     Длина текста: {len(trans.translated_text) if trans.translated_text else 0}")
            if trans.translated_text:
                print(f"     Начало текста: {trans.translated_text[:100]}...")
        
        # Проверяем, есть ли переведенный текст в самой главе
        if hasattr(ch, 'translated_text') and ch.translated_text:
            print(f"   Есть translated_text в главе: Да")
            print(f"   Длина translated_text: {len(ch.translated_text)}")
            print(f"   Начало текста: {ch.translated_text[:100]}...")
        else:
            print(f"   Есть translated_text в главе: Нет") 