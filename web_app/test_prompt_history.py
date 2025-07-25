#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы истории промптов
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Chapter, PromptHistory

def test_prompt_history():
    """Тестирование истории промптов"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Тестирование истории промптов...")
        
        # Проверяем, что таблица существует
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            if 'prompt_history' in tables:
                print("✅ Таблица prompt_history существует")
            else:
                print("❌ Таблица prompt_history не найдена")
                return False
        except Exception as e:
            print(f"❌ Ошибка при проверке таблиц: {e}")
            return False
        
        # Проверяем, есть ли главы в базе
        chapters = Chapter.query.limit(5).all()
        if not chapters:
            print("⚠️ В базе нет глав для тестирования")
            return True
        
        print(f"📚 Найдено {len(chapters)} глав для тестирования")
        
        # Проверяем историю промптов для каждой главы
        for chapter in chapters:
            print(f"\n📖 Глава {chapter.chapter_number}:")
            
            try:
                prompt_history = PromptHistory.query.filter_by(
                    chapter_id=chapter.id
                ).order_by(PromptHistory.created_at.desc()).all()
                
                if prompt_history:
                    print(f"  ✅ История промптов: {len(prompt_history)} записей")
                    
                    # Группируем по типам
                    types_count = {}
                    for prompt in prompt_history:
                        types_count[prompt.prompt_type] = types_count.get(prompt.prompt_type, 0) + 1
                    
                    for prompt_type, count in types_count.items():
                        print(f"    - {prompt_type}: {count}")
                else:
                    print(f"  ℹ️ История промптов пуста")
                    
            except Exception as e:
                print(f"  ❌ Ошибка при загрузке истории: {e}")
        
        # Тестируем создание тестовой записи
        print(f"\n🧪 Тестирование создания записи...")
        try:
            test_prompt = PromptHistory(
                chapter_id=chapters[0].id,
                prompt_type='test',
                system_prompt='Тестовый системный промпт',
                user_prompt='Тестовый пользовательский промпт',
                response='Тестовый ответ',
                success=True,
                model_used='test-model',
                temperature=0.1,
                execution_time=1.5
            )
            
            db.session.add(test_prompt)
            db.session.commit()
            print("✅ Тестовая запись создана успешно")
            
            # Удаляем тестовую запись
            db.session.delete(test_prompt)
            db.session.commit()
            print("✅ Тестовая запись удалена")
            
        except Exception as e:
            print(f"❌ Ошибка при создании тестовой записи: {e}")
            return False
        
        print("\n🎉 Тестирование завершено успешно!")
        return True

if __name__ == "__main__":
    success = test_prompt_history()
    if success:
        print("\n✅ Все тесты пройдены!")
    else:
        print("\n❌ Тесты завершились с ошибками!")
        sys.exit(1) 