#!/usr/bin/env python3
"""
Проверка статуса редактуры глав
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Chapter, PromptHistory

def check_editing_status():
    """Проверка статуса редактуры глав"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Проверка статуса редактуры глав...")
        
        # Проверяем все главы
        all_chapters = Chapter.query.all()
        print(f"📊 Всего глав: {len(all_chapters)}")
        
        # Статистика по статусам
        status_stats = {}
        for chapter in all_chapters:
            status = chapter.status or 'unknown'
            status_stats[status] = status_stats.get(status, 0) + 1
        
        print(f"\n📋 Статистика по статусам:")
        for status, count in status_stats.items():
            print(f"  {status}: {count}")
        
        # Проверяем главы со статусом 'edited'
        edited_chapters = Chapter.query.filter_by(status='edited').all()
        print(f"\n✏️ Глав со статусом 'edited': {len(edited_chapters)}")
        
        for chapter in edited_chapters:
            editing_prompts = PromptHistory.query.filter_by(
                chapter_id=chapter.id,
                prompt_type='editing_analysis'
            ).count()
            
            print(f"  Глава {chapter.chapter_number}: {editing_prompts} промптов редактуры")
        
        # Проверяем главы со статусом 'translated'
        translated_chapters = Chapter.query.filter_by(status='translated').all()
        print(f"\n📝 Глав со статусом 'translated': {len(translated_chapters)}")
        
        for chapter in translated_chapters[:5]:  # Показываем первые 5
            translation_prompts = PromptHistory.query.filter_by(
                chapter_id=chapter.id,
                prompt_type='translation'
            ).count()
            
            print(f"  Глава {chapter.chapter_number}: {translation_prompts} промптов перевода")
        
        # Проверяем, есть ли вообще промпты редактуры
        editing_prompts_total = PromptHistory.query.filter(
            PromptHistory.prompt_type.startswith('editing_')
        ).count()
        
        print(f"\n📊 Общая статистика промптов редактуры:")
        print(f"  Всего промптов редактуры: {editing_prompts_total}")
        
        if editing_prompts_total == 0:
            print(f"\n⚠️ ПРОБЛЕМА: Промпты редактуры не создаются!")
            print(f"  Возможные причины:")
            print(f"    1. Редактура не запускалась")
            print(f"    2. Редактура завершилась с ошибкой")
            print(f"    3. Промпты редактуры не сохраняются в БД")
            print(f"    4. Проблема в EditorService")
        else:
            print(f"\n✅ Промпты редактуры найдены: {editing_prompts_total}")

if __name__ == "__main__":
    check_editing_status() 