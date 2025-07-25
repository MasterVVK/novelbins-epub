#!/usr/bin/env python3
"""
Создание демонстрационных промптов редактуры для тестирования группировки
"""
import os
import sys
from datetime import datetime

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Chapter, PromptHistory

def create_demo_editing_prompts():
    """Создание демонстрационных промптов редактуры"""
    app = create_app()
    
    with app.app_context():
        print("🎭 Создание демонстрационных промптов редактуры...")
        
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
        
        # Создаем демонстрационные промпты редактуры
        editing_prompts = [
            {
                'type': 'editing_analysis',
                'system': 'Проанализируй качество переведенного текста',
                'user': 'Текст для анализа качества...',
                'response': 'КАЧЕСТВО: 7\nСТРАТЕГИЯ: style'
            },
            {
                'type': 'editing_style',
                'system': 'Улучши стиль переведенного текста',
                'user': 'Текст для улучшения стиля...',
                'response': 'Улучшенный текст с более плавными переходами...'
            },
            {
                'type': 'editing_dialogue',
                'system': 'Отполируй диалоги в тексте',
                'user': 'Текст с диалогами...',
                'response': 'Текст с отполированными диалогами...'
            },
            {
                'type': 'editing_final',
                'system': 'Сделай финальную полировку текста',
                'user': 'Текст для финальной полировки...',
                'response': 'Финально отполированный текст...'
            }
        ]
        
        # Создаем промпты с разными временными метками
        for i, prompt_data in enumerate(editing_prompts):
            # Создаем временную метку с небольшой задержкой
            timestamp = datetime.utcnow()
            
            prompt = PromptHistory(
                chapter_id=chapter_id,
                prompt_type=prompt_data['type'],
                system_prompt=prompt_data['system'],
                user_prompt=prompt_data['user'],
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
            print(f"  ✅ Создан промпт: {prompt_data['type']}")
        
        db.session.commit()
        print(f"\n✅ Создано {len(editing_prompts)} демонстрационных промптов редактуры")
        
        # Проверяем результат
        total_prompts = PromptHistory.query.filter_by(chapter_id=chapter_id).count()
        editing_prompts_count = PromptHistory.query.filter_by(
            chapter_id=chapter_id,
            prompt_type='editing_analysis'
        ).count()
        
        print(f"📊 Всего промптов для главы: {total_prompts}")
        print(f"📊 Промптов редактуры: {editing_prompts_count}")
        
        print(f"\n🎉 Теперь обновите страницу главы в браузере!")
        print(f"   Должны появиться секции 'Перевод' и 'Редактура'")

if __name__ == "__main__":
    create_demo_editing_prompts() 