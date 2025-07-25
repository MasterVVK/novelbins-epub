#!/usr/bin/env python3
"""
Миграция для удаления поля is_active из таблицы chapters
"""
import sqlite3
import os

def migrate_remove_is_active():
    """Удаление поля is_active из таблицы chapters"""
    db_path = 'instance/app.db'
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return
    
    print("🔄 Миграция: удаление поля is_active из таблицы chapters...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем информацию о таблице
        cursor.execute("PRAGMA table_info(chapters)")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"📋 Текущие поля таблицы chapters: {columns}")
        
        # Проверяем, существует ли поле is_active
        if 'is_active' not in columns:
            print("✅ Поле is_active уже удалено из таблицы chapters")
            return
        
        # Создаем новую таблицу без поля is_active
        print("🔄 Создание новой таблицы chapters без поля is_active...")
        
        # Получаем все поля кроме is_active
        columns_without_is_active = [col for col in columns if col != 'is_active']
        columns_sql = ', '.join(columns_without_is_active)
        
        # Создаем новую таблицу
        cursor.execute(f"""
            CREATE TABLE chapters_new (
                {columns_sql}
            )
        """)
        
        # Копируем данные (исключая поле is_active)
        placeholders = ', '.join(['?' for _ in columns_without_is_active])
        cursor.execute(f"""
            INSERT INTO chapters_new ({columns_sql})
            SELECT {columns_sql} FROM chapters
        """)
        
        # Удаляем старую таблицу и переименовываем новую
        cursor.execute("DROP TABLE chapters")
        cursor.execute("ALTER TABLE chapters_new RENAME TO chapters")
        
        # Сохраняем изменения
        conn.commit()
        
        print("✅ Миграция завершена успешно!")
        print("   - Поле is_active удалено из таблицы chapters")
        print("   - Все данные сохранены")
        print("   - Теперь используется полное удаление глав")
        
    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_remove_is_active() 