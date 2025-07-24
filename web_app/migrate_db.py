#!/usr/bin/env python3
"""
Миграция базы данных для добавления поля is_active в таблицу chapters
"""
import sqlite3
import os
from pathlib import Path

def migrate_chapters_table():
    """Добавление поля is_active в таблицу chapters"""
    
    # Путь к базе данных
    db_path = Path(__file__).parent / 'instance' / 'novel_translator.db'
    
    if not db_path.exists():
        print("❌ База данных не найдена")
        print(f"   Ожидаемый путь: {db_path}")
        print("   Сначала запустите веб-приложение для создания базы данных")
        return False
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем, существует ли уже поле is_active
        cursor.execute("PRAGMA table_info(chapters)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_active' in columns:
            print("✅ Поле is_active уже существует в таблице chapters")
            return True
        
        # Добавляем поле is_active
        print("🔄 Добавление поля is_active в таблицу chapters...")
        cursor.execute("ALTER TABLE chapters ADD COLUMN is_active BOOLEAN DEFAULT 1")
        
        # Обновляем существующие записи
        cursor.execute("UPDATE chapters SET is_active = 1 WHERE is_active IS NULL")
        
        # Сохраняем изменения
        conn.commit()
        conn.close()
        
        print("✅ Миграция успешно завершена")
        print("   - Добавлено поле is_active в таблицу chapters")
        print("   - Все существующие главы помечены как активные")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return False

def create_database():
    """Создание базы данных если она не существует"""
    from app import create_app, db
    from app.models.novel import Novel
    from app.models.chapter import Chapter
    from app.models.translation import Translation
    from app.models.task import Task
    from app.models.prompt_template import PromptTemplate
    from app.models.glossary import GlossaryItem
    from app.models.settings import SystemSettings
    
    app = create_app()
    with app.app_context():
        db.create_all()
        print("✅ База данных создана")

if __name__ == "__main__":
    print("=" * 60)
    print("МИГРАЦИЯ ТАБЛИЦЫ CHAPTERS")
    print("=" * 60)
    
    # Сначала создаем базу данных если её нет
    db_path = Path(__file__).parent / 'instance' / 'novel_translator.db'
    if not db_path.exists():
        print("📝 Создание базы данных...")
        create_database()
    
    # Затем выполняем миграцию
    success = migrate_chapters_table()
    
    if success:
        print("\n🎉 Миграция завершена успешно!")
        print("   Теперь можно использовать функциональность удаления глав")
    else:
        print("\n💥 Миграция завершена с ошибками!") 