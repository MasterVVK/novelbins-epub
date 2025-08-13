#!/usr/bin/env python3
"""
Детальный анализ базы данных с главами
"""

import sqlite3
import re
from collections import Counter

def analyze_database():
    """Анализируем базу данных с главами"""
    
    db_path = "web_app/instance/novel_translator.db"
    
    print(f"Анализ базы данных: {db_path}")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM chapters")
        total_chapters = cursor.fetchone()[0]
        print(f"📚 Всего глав в базе: {total_chapters}")
        
        # Статистика по статусам
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM chapters 
            GROUP BY status
            ORDER BY count DESC
        """)
        statuses = cursor.fetchall()
        print(f"\n📊 Статистика по статусам:")
        for status in statuses:
            print(f"  - {status['status']}: {status['count']} глав")
        
        # Ищем китайские главы (по содержанию китайских символов)
        print(f"\n🔍 ПОИСК КИТАЙСКИХ ГЛАВ")
        print("-" * 50)
        
        cursor.execute("""
            SELECT chapter_number, original_title, original_text, status,
                   LENGTH(original_text) as text_length
            FROM chapters 
            WHERE original_text IS NOT NULL 
                AND LENGTH(original_text) > 1000
                AND (original_title LIKE '%章%' OR original_text LIKE '%孟浩%')
            ORDER BY chapter_number 
            LIMIT 15
        """)
        
        chinese_chapters = cursor.fetchall()
        print(f"Найдено китайских глав с содержимым: {len(chinese_chapters)}")
        
        if chinese_chapters:
            print(f"\nПервые 10 китайских глав:")
            all_content = ""
            
            for i, chapter in enumerate(chinese_chapters[:10], 1):
                title = chapter['original_title'] or f"第{chapter['chapter_number']}章"
                content = chapter['original_text'] or ""
                
                # Подсчет китайских символов
                chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
                chinese_ratio = chinese_chars / len(content) if len(content) > 0 else 0
                
                print(f"\n{i}. {title}")
                print(f"   Номер главы: {chapter['chapter_number']}")
                print(f"   Статус: {chapter['status']}")
                print(f"   Длина: {chapter['text_length']} символов")
                print(f"   Китайские символы: {chinese_chars} ({chinese_ratio:.1%})")
                
                # Показываем начало главы
                preview = content[:200].replace('\n', ' ').strip()
                print(f"   Начало: {preview}{'...' if len(content) > 200 else ''}")
                
                all_content += "\n\n" + content
            
            if all_content.strip():
                print(f"\n🎨 АНАЛИЗ СОДЕРЖИМОГО ПЕРВЫХ 10 ГЛАВ")
                print("-" * 50)
                
                # Общая статистика текста
                total_chars = len(all_content)
                chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', all_content))
                
                print(f"Общее количество символов: {total_chars:,}")
                print(f"Китайские символы: {chinese_chars:,} ({chinese_chars/total_chars*100:.1f}%)")
                
                # Анализ персонажей
                print(f"\n👥 ОСНОВНЫЕ ПЕРСОНАЖИ")
                print("-" * 30)
                
                main_characters = {
                    '孟浩': 'Мэн Хао (главный герой)',
                    '许师姐': 'Сестра Сю (наставница)',
                    '王腾飞': 'Ван Тэнфэй',
                    '上官修': 'Шангуань Сю',
                    '赵武刚': 'Чжао Уган',
                    '韩宗': 'Хань Цзун',
                    '小胖子': 'Маленький толстяк',
                    '虎爷': 'Дедушка Ху',
                    '曹阳': 'Цао Ян'
                }
                
                for char, description in main_characters.items():
                    count = all_content.count(char)
                    if count > 0:
                        print(f"  - {char} ({description}): {count} упоминаний")
                
                # Анализ локаций
                print(f"\n🏔️ ОСНОВНЫЕ ЛОКАЦИИ")
                print("-" * 30)
                
                locations = {
                    '靠山宗': 'Секта Опоры на Гору (главная секта)',
                    '赵国': 'Государство Чжао',
                    '南域': 'Южный регион',
                    '东土': 'Восточная земля',
                    '大唐': 'Великая Тан',
                    '长安': 'Чанань (столица)',
                    '大青山': 'Большая зеленая гора',
                    '宝阁': 'Зал сокровищ',
                    '洞府': 'Пещерная резиденция'
                }
                
                for location, description in locations.items():
                    count = all_content.count(location)
                    if count > 0:
                        print(f"  - {location} ({description}): {count} упоминаний")
                
                # Анализ терминов культивации
                print(f"\n⚔️ ТЕРМИНЫ КУЛЬТИВАЦИИ")
                print("-" * 30)
                
                cultivation_terms = {
                    '凝气': 'Конденсация ци (уровень культивации)',
                    '修为': 'Уровень культивации',
                    '灵石': 'Духовные камни (валюта)',
                    '丹药': 'Пилюли (для улучшения)',
                    '内门': 'Внутренняя секта',
                    '外宗': 'Внешняя секта',
                    '杂役': 'Чернорабочие',
                    '长老': 'Старейшина',
                    '弟子': 'Ученик',
                    '师兄': 'Старший брат по учению',
                    '师姐': 'Старшая сестра по учению',
                    '仙人': 'Бессмертный',
                    '储物袋': 'Сумка хранения',
                    '铜镜': 'Медное зеркало (артефакт)'
                }
                
                for term, description in cultivation_terms.items():
                    count = all_content.count(term)
                    if count > 0:
                        print(f"  - {term} ({description}): {count} упоминаний")
                
                # Анализ стиля текста
                print(f"\n📝 СТИЛЬ ТЕКСТА")
                print("-" * 30)
                
                # Подсчет диалогов
                dialogue_count = len(re.findall(r'[""「」『』].+?[""「」『』]', all_content))
                sentences = len(re.findall(r'[。！？]', all_content))
                
                print(f"Предложения: {sentences}")
                print(f"Диалоги: {dialogue_count}")
                print(f"Соотношение диалогов: {dialogue_count/sentences*100:.1f}%" if sentences > 0 else "")
                
                # Анализ пунктуации
                punctuation = {
                    '。': 'Точки',
                    '！': 'Восклицания',
                    '？': 'Вопросы',
                    '，': 'Запятые',
                    '……': 'Многоточия'
                }
                
                print(f"\nПунктуация:")
                for punct, name in punctuation.items():
                    count = all_content.count(punct)
                    if count > 0:
                        print(f"  - {name} ({punct}): {count}")
        
        # Проверяем переводы
        print(f"\n🌍 АНАЛИЗ ПЕРЕВОДОВ")
        print("-" * 50)
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM translations 
            WHERE translated_text IS NOT NULL
        """)
        translated_count = cursor.fetchone()[0]
        print(f"Переведенных записей: {translated_count}")
        
        if translated_count > 0:
            cursor.execute("""
                SELECT t.original_text, t.translated_text, c.chapter_number
                FROM translations t
                JOIN chapters c ON t.chapter_id = c.id
                WHERE t.translated_text IS NOT NULL
                ORDER BY c.chapter_number
                LIMIT 5
            """)
            
            translations = cursor.fetchall()
            print(f"\nПримеры переводов:")
            for i, trans in enumerate(translations, 1):
                orig_preview = trans['original_text'][:100] if trans['original_text'] else ""
                trans_preview = trans['translated_text'][:100] if trans['translated_text'] else ""
                print(f"\n{i}. Глава {trans['chapter_number']}")
                print(f"   Оригинал: {orig_preview}...")
                print(f"   Перевод: {trans_preview}...")
        
        conn.close()
        
        print(f"\n✅ Анализ завершен!")
    
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    analyze_database()