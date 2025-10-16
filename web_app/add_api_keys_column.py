#!/usr/bin/env python3
"""
Добавляет колонку api_keys в таблицу ai_models
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

def add_api_keys_column():
    """Добавляет колонку api_keys в таблицу ai_models"""

    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("ДОБАВЛЕНИЕ КОЛОНКИ api_keys В ТАБЛИЦУ ai_models")
        print("=" * 60)

        try:
            # Используем прямой SQL для добавления колонки
            db.session.execute(db.text('ALTER TABLE ai_models ADD COLUMN api_keys TEXT'))
            db.session.commit()
            print("\n✅ Колонка api_keys успешно добавлена в таблицу ai_models")

        except Exception as e:
            if 'duplicate column name' in str(e).lower():
                print("\nℹ️  Колонка api_keys уже существует")
            else:
                print(f"\n❌ Ошибка при добавлении колонки: {e}")
                return False

        print("\n✅ Миграция схемы завершена!")
        return True

if __name__ == "__main__":
    try:
        success = add_api_keys_column()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
