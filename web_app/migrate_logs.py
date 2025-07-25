#!/usr/bin/env python3
"""
Миграция для добавления таблицы логов
"""
import sys
import os

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.log_entry import LogEntry
from sqlalchemy import text

app = create_app()

def migrate_logs():
    """Создание таблицы логов"""
    with app.app_context():
        try:
            # Создаем таблицу логов
            LogEntry.__table__.create(db.engine, checkfirst=True)
            print("✅ Таблица логов создана успешно")
            
            # Проверяем, что таблица создана
            with db.engine.connect() as conn:
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='log_entries'"))
                if result.fetchone():
                    print("✅ Таблица log_entries существует")
                else:
                    print("❌ Таблица log_entries не найдена")
                
        except Exception as e:
            print(f"❌ Ошибка создания таблицы логов: {e}")
            return False
    
    return True

if __name__ == '__main__':
    print("🔄 Начинаем миграцию логов...")
    if migrate_logs():
        print("✅ Миграция завершена успешно")
    else:
        print("❌ Миграция завершена с ошибками")
        sys.exit(1) 