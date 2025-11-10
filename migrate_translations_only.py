#!/usr/bin/env python3
"""
Миграция только таблицы translations
"""
import sys
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
import time

load_dotenv()

SQLITE_PATH = '/home/user/novelbins-epub/web_app/instance/novel_translator.db'
POSTGRES_URL = os.environ.get('DATABASE_URL')

def migrate_translations():
    print("=" * 70)
    print("🔄 МИГРАЦИЯ ТАБЛИЦЫ TRANSLATIONS")
    print("=" * 70)
    print()

    # Подключение
    sqlite_engine = create_engine(f'sqlite:///{SQLITE_PATH}')
    sqlite_session = sessionmaker(bind=sqlite_engine)()

    postgres_engine = create_engine(POSTGRES_URL)
    postgres_session = sessionmaker(bind=postgres_engine)()

    print("✅ Подключения установлены")

    # Очистка translations
    print("🧹 Очистка таблицы translations...")
    postgres_session.execute(text("TRUNCATE TABLE translations CASCADE"))
    postgres_session.commit()
    print("   ✅ Очищено")
    print()

    # Загружаем существующие chapter_id
    result = postgres_session.execute(text("SELECT id FROM chapters"))
    valid_chapter_ids = {row[0] for row in result.fetchall()}
    print(f"🔗 Загружено {len(valid_chapter_ids)} существующих chapter_id")

    # Получаем схему
    pg_inspector = inspect(postgres_engine)
    pg_columns = [col['name'] for col in pg_inspector.get_columns('translations')]

    # Читаем данные из SQLite
    print(f"📥 Чтение данных из SQLite...")
    result = sqlite_session.execute(text("SELECT * FROM translations"))
    sqlite_columns = list(result.keys())
    rows = result.fetchall()

    total = len(rows)
    print(f"📊 Записей в SQLite: {total}")

    # Общие колонки
    common_columns = [col for col in sqlite_columns if col in pg_columns]
    print(f"🔍 Общих колонок: {len(common_columns)}")
    print()

    # Формируем SQL
    columns_str = ', '.join([f'"{col}"' for col in common_columns])
    placeholders = ', '.join([f':{col}' for col in common_columns])
    insert_sql = f'INSERT INTO translations ({columns_str}) VALUES ({placeholders})'

    # Миграция
    print("📤 Вставка в PostgreSQL...")
    inserted = 0
    skipped = 0
    start_time = time.time()

    for i, row in enumerate(rows):
        # Создаем словарь
        row_dict = {}
        for idx, col in enumerate(sqlite_columns):
            if col in common_columns:
                row_dict[col] = row[idx]

        # Проверка chapter_id
        if 'chapter_id' in row_dict:
            if row_dict['chapter_id'] not in valid_chapter_ids:
                skipped += 1
                continue

        try:
            postgres_session.execute(text(insert_sql), row_dict)
            inserted += 1

            # Коммит каждые 100 записей
            if inserted % 100 == 0:
                postgres_session.commit()

            # Прогресс каждые 1000 записей
            if (inserted + skipped) % 1000 == 0:
                processed = inserted + skipped
                progress = (processed / total) * 100
                elapsed = time.time() - start_time
                rate = inserted / elapsed if elapsed > 0 else 0
                eta = (total - processed) / rate if rate > 0 else 0

                if skipped > 0:
                    print(f"   ⏳ {processed}/{total} ({progress:.1f}%) - вставлено: {inserted}, пропущено: {skipped} - {rate:.0f} зап/сек, ETA: {eta:.0f}с")
                else:
                    print(f"   ⏳ {processed}/{total} ({progress:.1f}%) - {rate:.0f} зап/сек, ETA: {eta:.0f}с")

        except Exception as e:
            print(f"   ❌ Ошибка на записи {inserted + skipped}: {e}")
            postgres_session.rollback()
            continue

    # Финальный коммит
    postgres_session.commit()

    # Обновление sequence
    max_id_result = postgres_session.execute(text("SELECT MAX(id) FROM translations"))
    max_id = max_id_result.scalar()
    if max_id:
        postgres_session.execute(text(f"SELECT setval('translations_id_seq', {max_id}, true)"))
        postgres_session.commit()
        print(f"   🔢 Sequence обновлена: max_id={max_id}")

    elapsed = time.time() - start_time

    print()
    print("=" * 70)
    print("✅ МИГРАЦИЯ ЗАВЕРШЕНА")
    print("=" * 70)
    print(f"📝 Вставлено: {inserted:,} записей")
    if skipped > 0:
        print(f"⚠️  Пропущено: {skipped:,} записей")
    print(f"⏱️  Время: {elapsed:.1f} секунд ({inserted/elapsed:.0f} зап/сек)")
    print()

    # Закрываем
    sqlite_session.close()
    postgres_session.close()

    return 0

if __name__ == '__main__':
    sys.exit(migrate_translations())
