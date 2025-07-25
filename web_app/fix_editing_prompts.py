#!/usr/bin/env python3
"""
Исправление типов существующих промптов редактуры
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import PromptHistory

def fix_editing_prompts():
    """Исправление типов промптов редактуры"""
    app = create_app()
    
    with app.app_context():
        print("🔧 Исправление типов промптов редактуры...")
        
        # Ищем промпты с системными промптами редактуры, но неправильными типами
        editing_keywords = [
            'Отполируй диалоги',
            'Улучши стиль',
            'Сделай финальную полировку',
            'Проанализируй качество'
        ]
        
        fixed_count = 0
        
        for keyword in editing_keywords:
            # Ищем промпты с ключевыми словами редактуры
            prompts = PromptHistory.query.filter(
                PromptHistory.system_prompt.contains(keyword),
                PromptHistory.prompt_type == 'translation'
            ).all()
            
            for prompt in prompts:
                # Определяем правильный тип на основе системного промпта
                if 'Отполируй диалоги' in prompt.system_prompt:
                    new_type = 'editing_dialogue'
                elif 'Улучши стиль' in prompt.system_prompt:
                    new_type = 'editing_style'
                elif 'Сделай финальную полировку' in prompt.system_prompt:
                    new_type = 'editing_final'
                elif 'Проанализируй качество' in prompt.system_prompt:
                    new_type = 'editing_analysis'
                else:
                    continue
                
                # Обновляем тип промпта
                old_type = prompt.prompt_type
                prompt.prompt_type = new_type
                fixed_count += 1
                
                print(f"  ✅ Исправлен промпт ID {prompt.id}: {old_type} → {new_type}")
                print(f"     Системный промпт: {prompt.system_prompt[:100]}...")
        
        if fixed_count > 0:
            db.session.commit()
            print(f"\n✅ Исправлено {fixed_count} промптов редактуры")
        else:
            print(f"\nℹ️ Промпты редактуры с неправильными типами не найдены")
        
        # Показываем статистику после исправления
        from sqlalchemy import func
        type_stats = db.session.query(
            PromptHistory.prompt_type,
            func.count(PromptHistory.id).label('count')
        ).group_by(PromptHistory.prompt_type).all()
        
        print(f"\n📊 Статистика после исправления:")
        for prompt_type, count in type_stats:
            print(f"  {prompt_type}: {count}")

if __name__ == "__main__":
    fix_editing_prompts() 