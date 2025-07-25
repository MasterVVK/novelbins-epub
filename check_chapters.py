#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter

app = create_app()

with app.app_context():
    novel = Novel.query.get(2)
    if novel:
        print(f"📚 Новелла: {novel.title}")
        print(f"📊 Всего глав: {len(Chapter.query.filter_by(novel_id=2, is_active=True).all())}")
        
        translated_chapters = Chapter.query.filter_by(novel_id=2, status='translated', is_active=True).all()
        print(f"✅ Переведенных глав: {len(translated_chapters)}")
        
        print(f"📋 Статусы глав:")
        for ch in Chapter.query.filter_by(novel_id=2, is_active=True).order_by(Chapter.chapter_number).all():
            print(f"  Глава {ch.chapter_number}: {ch.status}")
            
        if translated_chapters:
            print(f"\n🎯 Главы готовые для редактуры:")
            for ch in translated_chapters:
                print(f"  - Глава {ch.chapter_number}: {ch.original_title}")
        else:
            print(f"\n⚠️ Нет глав для редактуры!")
    else:
        print("❌ Новелла не найдена") 