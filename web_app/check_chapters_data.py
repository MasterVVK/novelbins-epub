#!/usr/bin/env python3
"""
Скрипт для проверки данных глав и их номеров
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Chapter, PromptHistory

def check_chapters_data():
    """Проверка данных глав и их номеров"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Проверка данных глав и их номеров...")
        
        # Проверяем все главы
        chapters = Chapter.query.order_by(Chapter.chapter_number).all()
        print(f"📚 Всего глав: {len(chapters)}")
        
        print(f"\n📖 Главы:")
        for chapter in chapters:
            print(f"  ID: {chapter.id}, Номер: {chapter.chapter_number}, Название: {chapter.original_title or 'Без названия'}")
        
        # Проверяем промпты по главам
        print(f"\n📝 Промпты по главам:")
        chapters_with_prompts = db.session.query(PromptHistory.chapter_id).distinct().all()
        
        for (chapter_id,) in chapters_with_prompts:
            chapter = Chapter.query.get(chapter_id)
            if chapter:
                prompt_count = PromptHistory.query.filter_by(chapter_id=chapter_id).count()
                print(f"  Глава {chapter.chapter_number} (ID: {chapter_id}): {prompt_count} промптов")
                
                # Показываем типы промптов
                prompt_types = db.session.query(PromptHistory.prompt_type).filter_by(chapter_id=chapter_id).distinct().all()
                types_list = [pt[0] for pt in prompt_types]
                print(f"    Типы: {types_list}")
        
        # Проверяем, есть ли дублирующиеся номера глав
        print(f"\n🔍 Проверка дублирующихся номеров глав:")
        chapter_numbers = [c.chapter_number for c in chapters]
        duplicates = [x for x in set(chapter_numbers) if chapter_numbers.count(x) > 1]
        
        if duplicates:
            print(f"  ⚠️ Найдены дублирующиеся номера: {duplicates}")
            for num in duplicates:
                dup_chapters = [c for c in chapters if c.chapter_number == num]
                print(f"    Номер {num}: {len(dup_chapters)} глав")
                for c in dup_chapters:
                    print(f"      - ID: {c.id}, Название: {c.original_title or 'Без названия'}")
        else:
            print(f"  ✅ Дублирующихся номеров глав нет")

if __name__ == "__main__":
    check_chapters_data() 