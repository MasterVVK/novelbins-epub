#!/usr/bin/env python3
"""
Скрипт для проверки наличия промптов в базе данных
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import PromptHistory

def check_prompts_in_db():
    """Проверка промптов в базе данных"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Проверка промптов в базе данных...")
        
        # Проверяем общее количество промптов
        total_prompts = PromptHistory.query.count()
        print(f"📊 Всего промптов в базе: {total_prompts}")
        
        if total_prompts == 0:
            print("⚠️ В базе данных нет промптов!")
            print("\n💡 Возможные причины:")
            print("   1. Функция сохранения промптов не включена")
            print("   2. Главы еще не переводились/редактировались")
            print("   3. Промпты были удалены")
            return
        
        # Показываем все промпты
        all_prompts = PromptHistory.query.order_by(PromptHistory.created_at.desc()).all()
        
        print(f"\n📝 Все промпты в базе:")
        for prompt in all_prompts:
            print(f"  ID: {prompt.id}, Глава: {prompt.chapter_id}, Тип: {prompt.prompt_type}, Успех: {prompt.success}")
        
        # Группируем по типам
        prompt_types = {}
        for prompt in all_prompts:
            if prompt.prompt_type not in prompt_types:
                prompt_types[prompt.prompt_type] = 0
            prompt_types[prompt.prompt_type] += 1
        
        print(f"\n🏷️ Распределение по типам:")
        for prompt_type, count in prompt_types.items():
            print(f"  {prompt_type}: {count}")
        
        # Группируем по главам
        chapter_prompts = {}
        for prompt in all_prompts:
            if prompt.chapter_id not in chapter_prompts:
                chapter_prompts[prompt.chapter_id] = []
            chapter_prompts[prompt.chapter_id].append(prompt)
        
        print(f"\n📖 Промпты по главам:")
        for chapter_id, prompts in chapter_prompts.items():
            print(f"  Глава {chapter_id}: {len(prompts)} промптов")
            for prompt in prompts:
                print(f"    - {prompt.prompt_type} (успех: {prompt.success})")

if __name__ == "__main__":
    check_prompts_in_db() 