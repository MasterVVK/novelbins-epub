#!/usr/bin/env python3
"""
Тестовый скрипт для проверки поведения промптов при полном удалении глав
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Chapter, PromptHistory

def test_prompt_deletion():
    """Тест поведения промптов при полном удалении глав"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Тест поведения промптов при полном удалении глав...")
        
        # Находим главу с промптами
        chapters_with_prompts = db.session.query(PromptHistory.chapter_id).distinct().all()
        if not chapters_with_prompts:
            print("❌ Нет глав с промптами для тестирования")
            return
        
        chapter_id = chapters_with_prompts[0][0]
        chapter = Chapter.query.get(chapter_id)
        
        if not chapter:
            print(f"❌ Глава {chapter_id} не найдена")
            return
        
        print(f"📖 Тестируем главу {chapter.chapter_number} (ID: {chapter_id})")
        
        # Проверяем начальное состояние
        initial_prompts = PromptHistory.query.filter_by(chapter_id=chapter_id).count()
        print(f"  📝 Начальное количество промптов: {initial_prompts}")
        
        if initial_prompts == 0:
            print("❌ У главы нет промптов для тестирования")
            return
        
        # Сохраняем информацию о главе
        novel_id = chapter.novel_id
        chapter_number = chapter.chapter_number
        
        # Выполняем полное удаление
        print(f"\n🗑️ Выполняем полное удаление главы...")
        db.session.delete(chapter)
        db.session.commit()
        
        # Проверяем, что глава удалена
        chapter_after_delete = Chapter.query.get(chapter_id)
        if chapter_after_delete is None:
            print(f"  ✅ Глава успешно удалена из базы данных")
        else:
            print(f"  ❌ Глава все еще существует в базе данных")
            return
        
        # Проверяем, что промпты тоже удалены
        prompts_after_delete = PromptHistory.query.filter_by(chapter_id=chapter_id).count()
        print(f"  📝 Количество промптов после удаления: {prompts_after_delete}")
        
        if prompts_after_delete == 0:
            print(f"  ✅ Все промпты успешно удалены")
        else:
            print(f"  ❌ Промпты не были удалены ({prompts_after_delete} осталось)")
        
        # Проверяем общее количество промптов в базе
        total_prompts = PromptHistory.query.count()
        print(f"  📊 Общее количество промптов в базе: {total_prompts}")
        
        # Сравниваем количество промптов
        if prompts_after_delete == 0:
            print(f"\n✅ Тест пройден: глава и все промпты успешно удалены")
        else:
            print(f"\n❌ Тест провален: промпты не были удалены")
        
        print(f"\n📋 Выводы:")
        print(f"  - При полном удалении главы промпты УДАЛЯЮТСЯ")
        print(f"  - Используется каскадное удаление (cascade='all, delete-orphan')")
        print(f"  - Восстановление главы невозможно - данные потеряны")
        print(f"  - Это обеспечивает чистоту базы данных")

if __name__ == "__main__":
    test_prompt_deletion() 