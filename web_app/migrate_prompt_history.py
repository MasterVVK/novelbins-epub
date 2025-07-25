#!/usr/bin/env python3
"""
Миграция для добавления таблицы prompt_history
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import PromptHistory

def migrate_prompt_history():
    """Создание таблицы prompt_history"""
    app = create_app()
    
    with app.app_context():
        print("🔧 Создание таблицы prompt_history...")
        
        try:
            # Создаем таблицу
            db.create_all()
            
            # Проверяем, что таблица создана
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'prompt_history' in tables:
                print("✅ Таблица prompt_history успешно создана")
                
                # Показываем структуру таблицы
                columns = inspector.get_columns('prompt_history')
                print("📋 Структура таблицы:")
                for column in columns:
                    print(f"  - {column['name']}: {column['type']}")
                    
            else:
                print("❌ Таблица prompt_history не найдена")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка при создании таблицы: {e}")
            return False
            
        return True

if __name__ == "__main__":
    success = migrate_prompt_history()
    if success:
        print("\n🎉 Миграция завершена успешно!")
    else:
        print("\n💥 Миграция завершена с ошибками!")
        sys.exit(1) 