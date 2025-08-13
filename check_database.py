#!/usr/bin/env python3
"""
Скрипт для проверки содержимого базы данных и анализа глав
"""

import sqlite3
import os
from collections import Counter
import re

def check_database_contents():
    """Проверяем содержимое базы данных"""
    
    # Ищем файл базы данных
    possible_db_paths = [
        "translations.db",
        "web_app/instance/translations.db",
        "web_app/translations.db",
        "instance/novel_translator.db",
        "web_app/instance/novel_translator.db"
    ]
    
    db_path = None
    for path in possible_db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ База данных не найдена. Поиск проводился в следующих местах:")
        for path in possible_db_paths:
            print(f"   - {path}")
        return
    
    print(f"📁 База данных найдена: {db_path}")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Проверяем структуру базы данных
        print("📋 СТРУКТУРА БАЗЫ ДАННЫХ")
        print("-" * 40)
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Таблицы: {', '.join(tables)}")
        print()
        
        # Проверяем содержимое таблицы chapters
        if 'chapters' in tables:
            print("📖 СОДЕРЖИМОЕ ТАБЛИЦЫ CHAPTERS")
            print("-" * 40)
            
            cursor.execute("SELECT COUNT(*) FROM chapters")
            total_chapters = cursor.fetchone()[0]
            print(f"Всего глав в базе: {total_chapters}")
            
            if total_chapters > 0:
                # Статистика по статусам
                cursor.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM chapters 
                    GROUP BY status
                """)
                statuses = cursor.fetchall()
                print("Статистика по статусам:")
                for status in statuses:
                    print(f"  - {status[0]}: {status[1]} глав")
                
                # Получаем первые 10 глав
                cursor.execute("""
                    SELECT chapter_number, original_title, 
                           LENGTH(original_text) as text_length,
                           status, translated_title
                    FROM chapters 
                    ORDER BY chapter_number 
                    LIMIT 10
                """)
                
                chapters = cursor.fetchall()
                print(f"\nПервые {len(chapters)} глав:")
                for chapter in chapters:
                    title = chapter['original_title'] or f"Глава {chapter['chapter_number']}"
                    translated_title = chapter['translated_title'] or "Не переведена"
                    print(f"  {chapter['chapter_number']:3d}. {title[:50]}{'...' if len(title) > 50 else ''}")
                    print(f"       Статус: {chapter['status']}, Символов: {chapter['text_length']}")
                    if chapter['translated_title']:
                        print(f"       Перевод: {translated_title[:50]}{'...' if len(translated_title) > 50 else ''}")
                    print()
                
                # Анализируем первые 10 глав с фактическим содержимым
                print("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ ПЕРВЫХ 10 ГЛАВ")
                print("-" * 40)
                
                cursor.execute("""
                    SELECT chapter_number, original_title, original_text, translated_title, translated_text
                    FROM chapters 
                    WHERE original_text IS NOT NULL AND LENGTH(original_text) > 100
                    ORDER BY chapter_number 
                    LIMIT 10
                """)
                
                detailed_chapters = cursor.fetchall()
                
                all_content = ""
                for i, chapter in enumerate(detailed_chapters, 1):
                    title = chapter['original_title'] or f"第{chapter['chapter_number']}章"
                    content = chapter['original_text'] or ""
                    
                    print(f"\n{i}. {title}")
                    print(f"   Номер главы: {chapter['chapter_number']}")
                    print(f"   Символов: {len(content)}")
                    
                    # Показываем начало главы
                    preview = content[:300].replace('\n', ' ').strip()
                    print(f"   Начало: {preview}{'...' if len(content) > 300 else ''}")
                    
                    if chapter['translated_title']:
                        print(f"   Переведенное название: {chapter['translated_title']}")
                    
                    all_content += "\n\n" + content
                
                if all_content.strip():
                    print(f"\n🎨 АНАЛИЗ СТИЛЯ И СОДЕРЖИМОГО")
                    print("-" * 40)
                    
                    # Анализируем китайский текст
                    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', all_content))
                    total_chars = len(all_content)
                    
                    print(f"Общее количество символов: {total_chars:,}")
                    print(f"Китайские символы: {chinese_chars:,} ({chinese_chars/total_chars*100:.1f}%)")
                    
                    # Ищем персонажей
                    print(f"\n👥 ПЕРСОНАЖИ И ИМЕНА")
                    print("-" * 20)
                    
                    # Основные персонажи из первых глав
                    main_characters = ['孟浩', '许师姐', '王腾飞', '上官修', '赵武刚', '韩宗']
                    for char in main_characters:
                        count = all_content.count(char)
                        if count > 0:
                            print(f"  - {char}: {count} упоминаний")
                    
                    # Ищем названия мест
                    print(f"\n🏔️ ЛОКАЦИИ")
                    print("-" * 20)
                    locations = ['靠山宗', '赵国', '南域', '东土', '大唐', '长安', '大青山']
                    for location in locations:
                        count = all_content.count(location)
                        if count > 0:
                            print(f"  - {location}: {count} упоминаний")
                    
                    # Ищем термины культивации
                    print(f"\n⚔️ ТЕРМИНЫ КУЛЬТИВАЦИИ")
                    print("-" * 20)
                    terms = ['凝气', '修为', '灵石', '丹药', '内门', '外宗', '杂役', '长老', '弟子']
                    for term in terms:
                        count = all_content.count(term)
                        if count > 0:
                            print(f"  - {term}: {count} упоминаний")
            else:
                print("База данных пуста - глав не найдено")
        
        # Проверяем глоссарий
        if 'glossary' in tables:
            print(f"\n📚 ГЛОССАРИЙ")
            print("-" * 40)
            
            cursor.execute("SELECT COUNT(*) FROM glossary")
            glossary_count = cursor.fetchone()[0]
            print(f"Записей в глоссарии: {glossary_count}")
            
            if glossary_count > 0:
                cursor.execute("""
                    SELECT category, COUNT(*) as count 
                    FROM glossary 
                    GROUP BY category
                """)
                categories = cursor.fetchall()
                for cat in categories:
                    print(f"  - {cat[0]}: {cat[1]} записей")
                
                # Показываем несколько примеров
                cursor.execute("SELECT english, russian, category FROM glossary LIMIT 10")
                examples = cursor.fetchall()
                if examples:
                    print("\nПримеры из глоссария:")
                    for ex in examples:
                        print(f"  {ex[0]} → {ex[1]} ({ex[2]})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при работе с базой данных: {e}")


if __name__ == "__main__":
    check_database_contents()