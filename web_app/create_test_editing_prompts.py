#!/usr/bin/env python3
"""
Скрипт для создания тестовых промптов редактуры
"""
import os
import sys
import time
from datetime import datetime

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Chapter, PromptHistory

def create_test_editing_prompts():
    """Создание тестовых промптов редактуры"""
    app = create_app()
    
    with app.app_context():
        print("🔧 Создание тестовых промптов редактуры...")
        
        # Находим главу с промптами перевода
        chapters_with_prompts = db.session.query(PromptHistory.chapter_id).distinct().all()
        if not chapters_with_prompts:
            print("❌ Нет глав с промптами для тестирования")
            return
        
        chapter_id = chapters_with_prompts[0][0]
        chapter = Chapter.query.get(chapter_id)
        
        if not chapter:
            print(f"❌ Глава {chapter_id} не найдена")
            return
        
        print(f"📖 Создаем промпты редактуры для главы {chapter.chapter_number} (ID: {chapter_id})")
        
        # Проверяем, есть ли уже промпты редактуры
        existing_editing = PromptHistory.query.filter_by(
            chapter_id=chapter_id,
            prompt_type='editing_analysis'
        ).first()
        
        if existing_editing:
            print("ℹ️ Промпты редактуры уже существуют")
            return
        
        # Создаем тестовые промпты редактуры
        editing_prompts = [
            {
                'prompt_type': 'editing_analysis',
                'system_prompt': 'Проанализируй качество переведенного текста',
                'user_prompt': 'Текст для анализа качества...',
                'response': 'КАЧЕСТВО: 7\nСТРАТЕГИЯ: style'
            },
            {
                'prompt_type': 'editing_style',
                'system_prompt': 'Улучши стиль переведенного текста',
                'user_prompt': 'Текст для улучшения стиля...',
                'response': 'Улучшенный текст...'
            },
            {
                'prompt_type': 'editing_dialogue',
                'system_prompt': 'Отполируй диалоги в тексте',
                'user_prompt': 'Текст с диалогами...',
                'response': 'Текст с отполированными диалогами...'
            },
            {
                'prompt_type': 'editing_final',
                'system_prompt': 'Сделай финальную полировку текста',
                'user_prompt': 'Текст для финальной полировки...',
                'response': 'Финально отполированный текст...'
            }
        ]
        
        # Создаем промпты с разными временными метками
        for i, prompt_data in enumerate(editing_prompts):
            # Создаем временную метку с небольшой задержкой
            timestamp = datetime.utcnow()
            
            prompt = PromptHistory(
                chapter_id=chapter_id,
                prompt_type=prompt_data['prompt_type'],
                system_prompt=prompt_data['system_prompt'],
                user_prompt=prompt_data['user_prompt'],
                response=prompt_data['response'],
                api_key_index=0,
                model_used='gemini-pro',
                temperature=0.2,
                tokens_used=1000 + i * 100,
                finish_reason='STOP',
                success=True,
                error_message=None,
                execution_time=5.0 + i,
                created_at=timestamp
            )
            
            db.session.add(prompt)
            print(f"  ✅ Создан промпт: {prompt_data['prompt_type']}")
        
        db.session.commit()
        print(f"\n✅ Создано {len(editing_prompts)} тестовых промптов редактуры")
        
        # Проверяем результат
        total_prompts = PromptHistory.query.filter_by(chapter_id=chapter_id).count()
        editing_prompts_count = PromptHistory.query.filter_by(
            chapter_id=chapter_id,
            prompt_type='editing_analysis'
        ).count()
        
        print(f"📊 Всего промптов для главы: {total_prompts}")
        print(f"📊 Промптов редактуры: {editing_prompts_count}")

if __name__ == "__main__":
    create_test_editing_prompts() 