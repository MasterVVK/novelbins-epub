#!/usr/bin/env python3
"""
Скрипт инициализации PostgreSQL базы данных
Создает все таблицы через SQLAlchemy
"""
import sys
import os
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

# Добавляем путь к web_app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'web_app'))

from app import create_app, db

def init_database():
    """Создание всех таблиц в PostgreSQL"""
    print("🔧 Инициализация PostgreSQL базы данных...")

    # Проверяем DATABASE_URL
    db_url = os.environ.get('DATABASE_URL')
    print(f"📍 DATABASE_URL: {db_url[:50] if db_url else 'НЕ УСТАНОВЛЕН'}...")

    # Создаем приложение
    app = create_app()

    with app.app_context():
        print(f"🔗 Используемая БД: {app.config['SQLALCHEMY_DATABASE_URI'][:60]}...")

        # Проверяем подключение
        try:
            conn = db.engine.connect()
            # Проверяем что это действительно PostgreSQL
            result = conn.execute(db.text("SELECT version()")).fetchone()
            version = result[0] if result else "unknown"
            if 'PostgreSQL' in version:
                print(f"✅ Подключение к PostgreSQL успешно")
                print(f"   Версия: {version[:80]}...")
            else:
                print(f"⚠️  Подключено к: {version[:80]}...")
            conn.close()
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return 1

        # Создаем все таблицы
        print("📊 Создаем таблицы...")
        try:
            db.create_all()
            print("✅ Все таблицы созданы")

            # Показываем список созданных таблиц
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"\n📋 Созданные таблицы ({len(tables)}):")
            for table in sorted(tables):
                print(f"  • {table}")

            print("\n🎉 База данных готова к использованию!")
            return 0

        except Exception as e:
            print(f"❌ Ошибка создания таблиц: {e}")
            return 1

if __name__ == '__main__':
    sys.exit(init_database())
