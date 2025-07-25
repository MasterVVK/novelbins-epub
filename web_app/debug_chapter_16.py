#!/usr/bin/env python3
"""
Отладочный скрипт для проверки группировки промптов главы 16
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Chapter, PromptHistory

def debug_chapter_16():
    """Отладка группировки промптов для главы 16"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Отладка группировки промптов для главы 16...")
        
        # Проверяем главу
        chapter = Chapter.query.get(16)
        if not chapter:
            print("❌ Глава 16 не найдена")
            return
        
        print(f"📖 Глава {chapter.chapter_number} (ID: {chapter.id})")
        
        try:
            prompt_history = PromptHistory.query.filter_by(
                chapter_id=16
            ).order_by(PromptHistory.created_at.desc()).all()
            
            if not prompt_history:
                print("  ℹ️ История промптов пуста")
                return
            
            print(f"  📝 Всего промптов: {len(prompt_history)}")
            
            # Показываем все типы промптов
            prompt_types = [p.prompt_type for p in prompt_history]
            print(f"  🏷️ Типы промптов: {prompt_types}")
            
            # Группируем промпты по категориям (как в views.py)
            translation_prompts = []
            editing_prompts = []
            
            for prompt in prompt_history:
                print(f"    Обрабатываем промпт типа: '{prompt.prompt_type}'")
                
                if prompt.prompt_type in ['translation', 'summary', 'terms_extraction']:
                    translation_prompts.append(prompt)
                    print(f"      -> Добавлен в перевод")
                elif prompt.prompt_type.startswith('editing_'):
                    editing_prompts.append(prompt)
                    print(f"      -> Добавлен в редактуру")
                else:
                    translation_prompts.append(prompt)
                    print(f"      -> Добавлен в перевод (неизвестный тип)")
            
            # Создаем структуру для шаблона
            prompt_groups = {
                'translation': translation_prompts,
                'editing': editing_prompts
            }
            
            print(f"\n  📊 Результат группировки:")
            print(f"    Перевод: {len(prompt_groups['translation'])} промптов")
            for p in prompt_groups['translation']:
                print(f"      - {p.prompt_type}")
            
            print(f"    Редактура: {len(prompt_groups['editing'])} промптов")
            for p in prompt_groups['editing']:
                print(f"      - {p.prompt_type}")
            
            # Проверяем, что передается в шаблон
            print(f"\n  🔧 Данные для шаблона:")
            print(f"    prompt_groups.keys(): {list(prompt_groups.keys())}")
            print(f"    prompt_groups['translation']: {len(prompt_groups['translation'])} элементов")
            print(f"    prompt_groups['editing']: {len(prompt_groups['editing'])} элементов")
            
            # Проверяем условия в шаблоне
            print(f"\n  🎯 Проверка условий шаблона:")
            print(f"    prompt_groups.translation: {bool(prompt_groups['translation'])}")
            print(f"    prompt_groups.editing: {bool(prompt_groups['editing'])}")
            
        except Exception as e:
            print(f"  ❌ Ошибка при обработке главы: {e}")

if __name__ == "__main__":
    debug_chapter_16() 