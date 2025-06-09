"""
database.py - Управление базой данных
"""
import sqlite3
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from models import Chapter, GlossaryItem, TranslationContext


class DatabaseManager:
    """Управление базой данных для хранения переводов и глоссария"""

    def __init__(self, db_path: str = "translations.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.init_database()

    def init_database(self):
        """Создание таблиц если их нет"""
        cursor = self.conn.cursor()

        # Таблица глав
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_number INTEGER UNIQUE NOT NULL,
                original_title TEXT,
                translated_title TEXT,
                original_text TEXT,
                translated_text TEXT,
                summary TEXT,
                url TEXT,
                word_count_original INTEGER,
                word_count_translated INTEGER,
                paragraph_count INTEGER,
                translated_at TIMESTAMP,
                translation_time REAL,
                status TEXT DEFAULT 'pending'
            )
        """)

        # Таблица глоссария
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS glossary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                english TEXT UNIQUE NOT NULL,
                russian TEXT NOT NULL,
                category TEXT NOT NULL,
                first_appearance_chapter INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица промптов для истории
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_number INTEGER,
                prompt_type TEXT,
                system_prompt TEXT,
                user_prompt TEXT,
                response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chapter_number) REFERENCES chapters(chapter_number)
            )
        """)

        # Таблица статистики API ключей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_index INTEGER,
                requests_count INTEGER DEFAULT 0,
                tokens_used INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                last_used TIMESTAMP,
                last_error TEXT
            )
        """)

        self.conn.commit()

    def save_parsed_chapter(self, chapter: Chapter) -> int:
        """Сохранение распарсенной главы"""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO chapters 
            (chapter_number, original_title, original_text, url,
             word_count_original, paragraph_count, status)
            VALUES (?, ?, ?, ?, ?, ?, 'parsed')
        """, (
            chapter.number,
            chapter.original_title,
            chapter.original_text,
            chapter.url,
            chapter.word_count,
            chapter.paragraph_count
        ))

        self.conn.commit()
        return cursor.lastrowid

    def update_chapter_translation(self, chapter: Chapter) -> None:
        """Обновление перевода главы"""
        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE chapters 
            SET translated_title = ?,
                translated_text = ?,
                summary = ?,
                word_count_translated = ?,
                translation_time = ?,
                translated_at = ?,
                status = 'completed'
            WHERE chapter_number = ?
        """, (
            chapter.translated_title,
            chapter.translated_text,
            chapter.summary,
            len(chapter.translated_text.split()) if chapter.translated_text else 0,
            chapter.translation_time,
            chapter.translated_at,
            chapter.number
        ))

        self.conn.commit()

    def get_chapters_for_translation(self) -> List[Chapter]:
        """Получение глав для перевода"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM chapters 
            WHERE status = 'parsed'
            ORDER BY chapter_number
        """)

        chapters = []
        for row in cursor.fetchall():
            chapter = Chapter(
                number=row['chapter_number'],
                original_title=row['original_title'],
                original_text=row['original_text'],
                url=row['url'],
                word_count=row['word_count_original'],
                paragraph_count=row['paragraph_count']
            )
            chapters.append(chapter)

        return chapters

    def get_translated_chapters(self, chapter_numbers: Optional[List[int]] = None) -> List[Chapter]:
        """Получение переведённых глав"""
        cursor = self.conn.cursor()

        if chapter_numbers:
            placeholders = ','.join('?' * len(chapter_numbers))
            query = f"""
                SELECT * FROM chapters
                WHERE status = 'completed' AND chapter_number IN ({placeholders})
                ORDER BY chapter_number
            """
            cursor.execute(query, chapter_numbers)
        else:
            cursor.execute("""
                SELECT * FROM chapters
                WHERE status = 'completed'
                ORDER BY chapter_number
            """)

        chapters = []
        for row in cursor.fetchall():
            chapter = Chapter(
                number=row['chapter_number'],
                original_title=row['original_title'],
                original_text=row['original_text'],
                url=row['url'],
                word_count=row['word_count_original'],
                paragraph_count=row['paragraph_count'],
                translated_title=row['translated_title'],
                translated_text=row['translated_text'],
                summary=row['summary'],
                translation_time=row['translation_time'],
                translated_at=row['translated_at']
            )
            chapters.append(chapter)

        return chapters

    def save_glossary_item(self, item: GlossaryItem) -> None:
        """Сохранение элемента глоссария"""
        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO glossary (english, russian, category, first_appearance_chapter, description)
                VALUES (?, ?, ?, ?, ?)
            """, (
                item.english,
                item.russian,
                item.category,
                item.first_appearance_chapter,
                item.description
            ))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Элемент уже существует
            pass

    def get_glossary(self) -> Dict[str, Dict[str, str]]:
        """Получение всего глоссария"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT english, russian, category FROM glossary")

        glossary = {'characters': {}, 'locations': {}, 'terms': {}}
        for row in cursor.fetchall():
            category_map = {
                'character': 'characters',
                'location': 'locations',
                'term': 'terms'
            }
            category = category_map.get(row['category'], 'terms')
            glossary[category][row['english']] = row['russian']

        return glossary

    def get_recent_summaries(self, limit: int = 2) -> List[Dict[str, str]]:
        """Получение последних резюме глав"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT chapter_number, summary 
            FROM chapters 
            WHERE status = 'completed' AND summary IS NOT NULL
            ORDER BY chapter_number DESC 
            LIMIT ?
        """, (limit,))

        summaries = []
        for row in cursor.fetchall():
            summaries.append({
                'chapter': row['chapter_number'],
                'summary': row['summary']
            })

        return list(reversed(summaries))

    def get_translation_context(self, chapter_number: int) -> TranslationContext:
        """Получение контекста для перевода главы"""
        # Получаем резюме предыдущих глав
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT chapter_number, summary 
            FROM chapters 
            WHERE status = 'completed' AND summary IS NOT NULL
                AND chapter_number < ?
            ORDER BY chapter_number DESC 
            LIMIT 2
        """, (chapter_number,))

        summaries = []
        for row in cursor.fetchall():
            summaries.append({
                'chapter': row['chapter_number'],
                'summary': row['summary']
            })
        summaries = list(reversed(summaries))

        # Получаем глоссарий
        glossary = self.get_glossary()

        return TranslationContext(
            previous_summaries=summaries,
            glossary=glossary
        )

    def save_prompt(self, chapter_number: int, prompt_type: str,
                   system_prompt: str, user_prompt: str, response: str) -> None:
        """Сохранение промпта и ответа"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO prompts (chapter_number, prompt_type, system_prompt, user_prompt, response)
            VALUES (?, ?, ?, ?, ?)
        """, (chapter_number, prompt_type, system_prompt, user_prompt, response))
        self.conn.commit()

    def update_api_stats(self, key_index: int, success: bool = True, error: str = None) -> None:
        """Обновление статистики использования API ключей"""
        cursor = self.conn.cursor()

        # Проверяем, есть ли запись для этого ключа
        cursor.execute("SELECT id FROM api_stats WHERE api_key_index = ?", (key_index,))
        row = cursor.fetchone()

        if row:
            # Обновляем существующую запись
            if success:
                cursor.execute("""
                    UPDATE api_stats 
                    SET requests_count = requests_count + 1,
                        last_used = CURRENT_TIMESTAMP
                    WHERE api_key_index = ?
                """, (key_index,))
            else:
                cursor.execute("""
                    UPDATE api_stats 
                    SET errors_count = errors_count + 1,
                        last_error = ?,
                        last_used = CURRENT_TIMESTAMP
                    WHERE api_key_index = ?
                """, (error, key_index))
        else:
            # Создаём новую запись
            cursor.execute("""
                INSERT INTO api_stats (api_key_index, requests_count, errors_count, last_error, last_used)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (key_index, 1 if success else 0, 0 if success else 1, error))

        self.conn.commit()

    def get_statistics(self) -> Dict:
        """Получение общей статистики"""
        cursor = self.conn.cursor()

        # Статистика глав
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'parsed' THEN 1 ELSE 0 END) as parsed,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
            FROM chapters
        """)
        chapters_stats = cursor.fetchone()

        # Статистика глоссария
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM glossary
            GROUP BY category
        """)
        glossary_stats = {row['category']: row['count'] for row in cursor.fetchall()}

        # Статистика API
        cursor.execute("""
            SELECT 
                COUNT(*) as keys_used,
                SUM(requests_count) as total_requests,
                SUM(errors_count) as total_errors
            FROM api_stats
        """)
        api_stats = cursor.fetchone()

        return {
            'chapters': {
                'total': chapters_stats['total'],
                'parsed': chapters_stats['parsed'],
                'completed': chapters_stats['completed']
            },
            'glossary': glossary_stats,
            'api': {
                'keys_used': api_stats['keys_used'],
                'total_requests': api_stats['total_requests'] or 0,
                'total_errors': api_stats['total_errors'] or 0
            }
        }

    def close(self):
        """Закрытие соединения с БД"""
        self.conn.close()

    def get_existing_chapter_numbers(self) -> set:
        """Получение номеров уже существующих глав"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT chapter_number FROM chapters")
        return {row[0] for row in cursor.fetchall()}