#!/usr/bin/env python3
"""
check_chapter_4_translation.py - Проверяем, что сохранено для главы 4
"""
import sqlite3
from pathlib import Path

def check_chapter_4():
    # Проверяем файл перевода
    translation_file = Path("translations/chapter_004_ru.txt")

    if translation_file.exists():
        print(" НАЙДЕН ФАЙЛ ПЕРЕВОДА:")
        print(f"   Путь: {translation_file}")

        with open(translation_file, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"   Размер: {len(content)} символов")
        print(f"   Первые 500 символов:")
        print("-" * 60)
        print(content[:500])
        print("-" * 60)

        # Проверяем на подозрительный контент
        if "Пропущена из-за блокировки" in content:
            print("\n⚠️ Глава помечена как пропущенная!")

    else:
        print("❌ Файл перевода НЕ найден")

    # Проверяем БД
    db_path = Path("translations.db")

    if db_path.exists():
        print("\n ПРОВЕРКА БАЗЫ ДАННЫХ:")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                chapter_number,
                status,
                translated_title,
                LENGTH(original_text) as orig_len,
                LENGTH(translated_text) as trans_len,
                summary,
                translated_at
            FROM chapters 
            WHERE chapter_number = 4
        """)

        row = cursor.fetchone()

        if row:
            print(f"   Номер главы: {row[0]}")
            print(f"   Статус: {row[1]}")
            print(f"   Переведённое название: {row[2]}")
            print(f"   Размер оригинала: {row[3]} символов")
            print(f"   Размер перевода: {row[4] if row[4] else 0} символов")
            print(f"   Резюме: {'Есть' if row[5] else 'Отсутствует'}")
            print(f"   Время перевода: {row[6]}")

            if row[5]:
                print(f"\n   Текст резюме:")
                print(f"   {row[5]}")

        else:
            print("   Глава 4 НЕ найдена в БД")

        # Проверяем промпты
        cursor.execute("""
            SELECT prompt_type, created_at, LENGTH(response) as response_len
            FROM prompts
            WHERE chapter_number = 4
            ORDER BY created_at
        """)

        prompts = cursor.fetchall()

        if prompts:
            print(f"\n   ИСТОРИЯ ПРОМПТОВ:")
            for p in prompts:
                print(f"   - {p[0]}: {p[1]} (ответ: {p[2]} символов)")

        conn.close()

    else:
        print("\n❌ База данных НЕ найдена")


if __name__ == "__main__":
    print(" ПРОВЕРКА СОСТОЯНИЯ ГЛАВЫ 4")
    print("="*80)

    check_chapter_4()