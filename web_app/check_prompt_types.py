#!/usr/bin/env python3
"""
Скрипт для проверки всех типов промптов в базе данных
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import PromptHistory
from sqlalchemy import func

def check_prompt_types():
    """Проверка всех типов промптов в базе"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Проверка всех типов промптов в базе данных...")
        
        # Получаем статистику по типам промптов
        type_stats = db.session.query(
            PromptHistory.prompt_type,
            func.count(PromptHistory.id).label('count')
        ).group_by(PromptHistory.prompt_type).all()
        
        if not type_stats:
            print("❌ Нет промптов в базе данных")
            return
        
        print(f"📊 Статистика по типам промптов:")
        total_prompts = 0
        
        for prompt_type, count in type_stats:
            total_prompts += count
            print(f"  {prompt_type}: {count}")
        
        print(f"\n📈 Всего промптов: {total_prompts}")
        
        # Анализируем группировку
        print(f"\n🧪 Анализ группировки:")
        
        translation_types = ['translation', 'summary', 'terms_extraction']
        editing_types = []
        other_types = []
        
        for prompt_type, count in type_stats:
            if prompt_type in translation_types:
                print(f"  {prompt_type} → группа 'Перевод'")
            elif prompt_type.startswith('editing_'):
                editing_types.append(prompt_type)
                print(f"  {prompt_type} → группа 'Редактура'")
            else:
                other_types.append(prompt_type)
                print(f"  {prompt_type} → группа 'Перевод' (неизвестный тип)")
        
        # Подсчитываем общие количества
        translation_count = sum(count for prompt_type, count in type_stats if prompt_type in translation_types)
        editing_count = sum(count for prompt_type, count in type_stats if prompt_type.startswith('editing_'))
        other_count = sum(count for prompt_type, count in type_stats if prompt_type not in translation_types and not prompt_type.startswith('editing_'))
        
        print(f"\n📊 Итоговая группировка:")
        print(f"  Перевод: {translation_count} промптов")
        print(f"  Редактура: {editing_count} промптов")
        print(f"  Другие (в перевод): {other_count} промптов")
        
        # Проверяем, есть ли промпты редактуры
        if editing_count == 0:
            print(f"\n⚠️ ПРОБЛЕМА: Нет промптов редактуры!")
            print(f"  Это объясняет, почему все промпты отображаются в группе 'Перевод'")
            print(f"  Решение: запустить редактуру глав для создания промптов с типами editing_*")
        else:
            print(f"\n✅ Промпты редактуры найдены: {editing_count}")
            print(f"  Типы: {', '.join(editing_types)}")

if __name__ == "__main__":
    check_prompt_types() 