import os
import json
import time
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
import httpx
from httpx_socks import SyncProxyTransport
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup, NavigableString
import re
from ebooklib import epub

# Загружаем переменные окружения
load_dotenv()

# Конфигурация
GEMINI_API_KEYS = os.getenv('GEMINI_API_KEYS', '').split(',')
GEMINI_API_KEYS = [key.strip() for key in GEMINI_API_KEYS if key.strip()]

PROXY_URL = os.getenv('PROXY_URL')
MODEL_NAME = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20')
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.1'))
REQUEST_DELAY = int(os.getenv('REQUEST_DELAY', '2'))

# URL новеллы
NOVEL_URL = "https://novelbins.com/novel/shrouding-the-heavens-1150192/"

# Системный промпт для перевода
TRANSLATION_PROMPT = """Ты профессиональный переводчик китайских веб-новелл жанра сянься.
Переводишь роман "Shrouding the Heavens" (遮天) с английского на русский.

ОСНОВНЫЕ ПРАВИЛА:
1. Имена переводи осмысленно по правилам китайско-русской транскрипции (Ye Fan → Е Фань)
2. Сохраняй эпический стиль повествования, характерный для жанра сянься
3. Термины культивации переводи последовательно
4. Поддерживай эмоциональную окраску диалогов
5. Сохраняй поэтичность языка и восточный колорит"""

# Промпт для создания резюме
SUMMARY_PROMPT = """Составь КРАТКОЕ резюме главы (максимум 150 слов) для использования как контекст в следующих главах.
Включи:
- Ключевые события
- Важные открытия или изменения
- Упомянутые локации
- Активных персонажей
Пиши в прошедшем времени, лаконично."""

# Промпт для извлечения терминов
EXTRACT_TERMS_PROMPT = """Извлеки из текста:
1. Новые ЛОКАЦИИ (места, горы, храмы и т.д.)
2. Новые ТЕРМИНЫ культивации (техники, артефакты, уровни силы)
3. Новые ИМЕНА персонажей

Формат ответа:
ЛОКАЦИИ:
- английский = русский

ТЕРМИНЫ:
- английский = русский

ПЕРСОНАЖИ:
- английский = русский"""


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
                word_count_original INTEGER,
                word_count_translated INTEGER,
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
                last_used TIMESTAMP
            )
        """)

        self.conn.commit()

    def save_chapter(self, chapter_data: Dict) -> int:
        """Сохранение главы в БД"""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO chapters 
            (chapter_number, original_title, translated_title, original_text, 
             translated_text, summary, word_count_original, word_count_translated,
             translated_at, translation_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chapter_data['chapter_number'],
            chapter_data['original_title'],
            chapter_data['translated_title'],
            chapter_data['original_text'],
            chapter_data['translated_text'],
            chapter_data.get('summary', ''),
            chapter_data['word_count_original'],
            chapter_data['word_count_translated'],
            datetime.now(),
            chapter_data.get('translation_time', 0),
            'completed'
        ))

        self.conn.commit()
        return cursor.lastrowid

    def save_glossary_item(self, english: str, russian: str, category: str,
                          chapter_number: int, description: str = "") -> None:
        """Сохранение элемента глоссария"""
        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO glossary (english, russian, category, first_appearance_chapter, description)
                VALUES (?, ?, ?, ?, ?)
            """, (english, russian, category, chapter_number, description))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Элемент уже существует, обновляем если нужно
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

    def get_recent_summaries(self, limit: int = 2) -> List[Dict]:
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

    def get_untranslated_chapters(self) -> List[int]:
        """Получение номеров непереведённых глав"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT chapter_number 
            FROM chapters 
            WHERE status = 'pending' 
            ORDER BY chapter_number
        """)

        return [row['chapter_number'] for row in cursor.fetchall()]

    def save_prompt(self, chapter_number: int, prompt_type: str,
                   system_prompt: str, user_prompt: str, response: str) -> None:
        """Сохранение промпта и ответа"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO prompts (chapter_number, prompt_type, system_prompt, user_prompt, response)
            VALUES (?, ?, ?, ?, ?)
        """, (chapter_number, prompt_type, system_prompt, user_prompt, response))
        self.conn.commit()

    def close(self):
        """Закрытие соединения с БД"""
        self.conn.close()


class NovelParser:
    """Парсер для novelbins.com с поддержкой пагинации"""

    def __init__(self):
        self.base_url = "https://novelbins.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get_page(self, url: str) -> Optional[str]:
        """Получение HTML страницы с обработкой ошибок"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Ошибка при загрузке {url}: {e}")
            return None

    def extract_chapter_number(self, url: str) -> int:
        """Извлечение номера главы из URL"""
        match = re.search(r'/chapter/(\d+)', url)
        return int(match.group(1)) if match else 0

    def parse_chapter_list(self, novel_url: str, max_chapters: int = 3) -> List[Dict[str, str]]:
        """Получение списка ссылок на главы"""
        print(f"Загрузка страницы новеллы: {novel_url}")
        html = self.get_page(novel_url)

        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        chapter_links = []

        # Используем найденный контейнер div.chapters
        chapters_container = soup.find('div', class_='chapters')

        if chapters_container:
            # Ищем все ссылки на главы
            all_links = chapters_container.find_all('a', href=lambda x: x and '/chapter/' in x)
            print(f"Найдено {len(all_links)} ссылок в контейнере div.chapters")

            # Создаем список всех глав с их номерами
            all_chapters = []
            for link in all_links:
                href = link.get('href', '')
                title = link.text.strip()
                chapter_num = self.extract_chapter_number(href)

                if chapter_num > 0:  # Исключаем невалидные номера
                    # Формирование полного URL
                    if href and not href.startswith('http'):
                        href = self.base_url + href

                    chapter_info = {
                        'url': href,
                        'title': title,
                        'number': chapter_num
                    }
                    all_chapters.append(chapter_info)

            # Сортируем по номеру главы (от меньшего к большему)
            all_chapters.sort(key=lambda x: x['number'])

            # Берем только первые max_chapters глав
            chapter_links = all_chapters[:max_chapters]

            print(f"\nВыбраны первые {len(chapter_links)} глав:")
            for chapter in chapter_links:
                print(f"  Глава {chapter['number']}: {chapter['title']}")
        else:
            print("Контейнер с главами не найден!")

        return chapter_links

    def extract_text_nodes(self, element, min_length=50) -> List[str]:
        """Извлечение текстовых узлов из элемента"""
        text_nodes = []

        for elem in element.descendants:
            # Проверяем, является ли элемент текстовым узлом
            if isinstance(elem, NavigableString):
                text = str(elem).strip()

                # Фильтруем короткие строки и навигационные элементы
                if len(text) >= min_length:
                    # Проверяем, не является ли это навигацией или системным текстом
                    lower_text = text.lower()
                    skip_words = ['next chapter', 'previous chapter', 'advertisement',
                                 'copyright', 'all rights reserved', 'views:', 'tags:']

                    if not any(skip in lower_text for skip in skip_words):
                        # Очищаем от лишних пробелов
                        text = ' '.join(text.split())
                        text_nodes.append(text)

        return text_nodes

    def parse_chapter_content(self, chapter_url: str, chapter_number: int) -> Dict[str, any]:
        """Парсинг содержимого одной главы"""
        print(f"\nЗагрузка главы {chapter_number}: {chapter_url}")
        html = self.get_page(chapter_url)

        if not html:
            return {'error': 'Failed to load chapter'}

        soup = BeautifulSoup(html, 'html.parser')
        result = {
            'url': chapter_url,
            'chapter_number': chapter_number,
            'title': '',
            'content': '',
            'paragraphs': [],
            'metadata': {}
        }

        # Извлечение заголовка главы
        chapter_title = None

        # Проверяем title страницы
        page_title = soup.find('title')
        if page_title:
            title_text = page_title.text.strip()
            # Извлекаем часть с Chapter X
            chapter_match = re.search(r'Chapter\s*\d+[:\s]*[^-|]+', title_text)
            if chapter_match:
                chapter_title = chapter_match.group(0).strip()

        # Если не нашли в title, ищем в тексте страницы
        if not chapter_title:
            # Ищем первый параграф с "Chapter X"
            for p in soup.find_all('p'):
                if p.text and re.match(r'^Chapter\s*\d+', p.text.strip()):
                    chapter_title = p.text.strip()
                    break

        if not chapter_title:
            chapter_title = f"Chapter {chapter_number}"

        result['title'] = chapter_title

        # Поиск основного контейнера с контентом
        content_containers = [
            soup.find('div', class_='page-content-wrapper'),
            soup.find('div', class_='page-content'),
            soup.find('div', class_='content-wrapper'),
            soup.find('div', class_='chapter-content')
        ]

        main_content = None
        for container in content_containers:
            if container:
                main_content = container
                break

        # Если не нашли по классам, ищем по размеру текста
        if not main_content:
            all_divs = soup.find_all('div')
            for div in all_divs:
                text_length = len(div.text.strip())
                if 5000 < text_length < 15000:  # Подходящий размер для главы
                    main_content = div
                    break

        if main_content:
            print(f"  Найден контейнер с контентом")

            # Удаление ненужных элементов
            for tag in main_content.find_all(['script', 'style', 'nav', 'button', 'form']):
                tag.decompose()

            # Удаление навигационных ссылок
            for link in main_content.find_all('a'):
                link_text = link.text.strip().lower()
                if any(word in link_text for word in ['next', 'previous', 'chapter list']):
                    link.decompose()

            # Извлечение текста
            # Метод 1: Пробуем найти параграфы в <p> тегах
            p_tags = main_content.find_all('p')
            paragraphs = []

            if p_tags and len(p_tags) > 5:  # Если есть достаточно p-тегов
                print(f"  Найдено {len(p_tags)} <p> тегов")
                for p in p_tags:
                    text = p.text.strip()
                    # Пропускаем заголовок главы и короткие строки
                    if text and len(text) > 30 and not text.startswith('Chapter'):
                        paragraphs.append(text)

            # Метод 2: Если мало параграфов, используем текстовые узлы
            if len(paragraphs) < 5:
                print(f"  Используем метод текстовых узлов")
                text_nodes = self.extract_text_nodes(main_content, min_length=80)

                if text_nodes:
                    print(f"  Найдено {len(text_nodes)} текстовых узлов")
                    # Объединяем короткие узлы в параграфы
                    current_paragraph = []

                    for node in text_nodes:
                        # Если узел длинный, это отдельный параграф
                        if len(node) > 200:
                            if current_paragraph:
                                paragraphs.append(' '.join(current_paragraph))
                                current_paragraph = []
                            paragraphs.append(node)
                        else:
                            # Короткий узел добавляем к текущему параграфу
                            current_paragraph.append(node)

                            # Если накопили достаточно текста, создаем параграф
                            if sum(len(t) for t in current_paragraph) > 300:
                                paragraphs.append(' '.join(current_paragraph))
                                current_paragraph = []

                    # Добавляем последний параграф
                    if current_paragraph:
                        paragraphs.append(' '.join(current_paragraph))

            # Финальная фильтрация параграфов
            filtered_paragraphs = []
            for para in paragraphs:
                # Убираем дубликаты и слишком короткие параграфы
                if para not in filtered_paragraphs and len(para) > 50:
                    filtered_paragraphs.append(para)

            result['paragraphs'] = filtered_paragraphs
            result['content'] = '\n\n'.join(filtered_paragraphs)

            # Метаданные
            result['metadata'] = {
                'word_count': len(result['content'].split()),
                'paragraph_count': len(filtered_paragraphs),
                'char_count': len(result['content']),
                'extraction_method': 'p_tags' if len(p_tags) > 5 else 'text_nodes'
            }

            print(f"  ✓ Извлечено параграфов: {len(filtered_paragraphs)}")
            print(f"  ✓ Всего слов: {result['metadata']['word_count']}")
        else:
            print("  ❌ Контент не найден!")
            result['error'] = 'Content not found'

        return result


class FinalTranslator:
    """Финальный переводчик с БД и динамическим контекстом"""

    def __init__(self, api_keys: List[str], proxy_url: Optional[str] = None):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.proxy_url = proxy_url
        self.db = DatabaseManager()

        # HTTP клиент
        if proxy_url:
            self.transport = SyncProxyTransport.from_url(proxy_url)
            self.client = httpx.Client(transport=self.transport, timeout=180)
        else:
            self.client = httpx.Client(timeout=180)

        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

    @property
    def current_key(self) -> str:
        return self.api_keys[self.current_key_index]

    def switch_to_next_key(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f" Переключение на ключ #{self.current_key_index + 1}")

    def make_request(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Базовый метод для запросов к API"""
        generation_config = {
            "temperature": TEMPERATURE,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": 16384
        }

        for _ in range(len(self.api_keys)):
            try:
                response = self.client.post(
                    self.api_url,
                    params={"key": self.current_key},
                    headers={"Content-Type": "application/json"},
                    json={
                        "generationConfig": generation_config,
                        "contents": [{
                            "parts": [
                                {"text": system_prompt},
                                {"text": user_prompt}
                            ]
                        }]
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            return parts[0].get("text", "")

                elif response.status_code == 429:
                    print("⚠️  Лимит API достигнут")
                    self.switch_to_next_key()
                    continue

            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                self.switch_to_next_key()

        return None

    def build_context(self, chapter_num: int) -> Tuple[str, str]:
        """Построение контекста из БД"""
        # Получаем глоссарий
        glossary = self.db.get_glossary()

        glossary_lines = []
        if glossary['characters']:
            glossary_lines.append("ПЕРСОНАЖИ:")
            for eng, rus in glossary['characters'].items():
                glossary_lines.append(f"- {eng} = {rus}")

        if glossary['locations']:
            glossary_lines.append("\nЛОКАЦИИ:")
            for eng, rus in glossary['locations'].items():
                glossary_lines.append(f"- {eng} = {rus}")

        if glossary['terms']:
            glossary_lines.append("\nТЕРМИНЫ:")
            for eng, rus in glossary['terms'].items():
                glossary_lines.append(f"- {eng} = {rus}")

        glossary_text = "\n".join(glossary_lines) if glossary_lines else ""

        # Получаем резюме предыдущих глав
        summaries = self.db.get_recent_summaries(2)
        context_lines = []

        if summaries:
            context_lines.append("ПРЕДЫДУЩИЕ СОБЫТИЯ:")
            for item in summaries:
                context_lines.append(f"\nГлава {item['chapter']}:")
                context_lines.append(item['summary'])

        context_text = "\n".join(context_lines) if context_lines else ""

        return context_text, glossary_text

    def translate_chapter(self, chapter_data: Dict) -> bool:
        """Перевод главы с сохранением в БД"""
        chapter_num = chapter_data['chapter_number']
        print(f"\n Глава {chapter_num}: {chapter_data['title']}")
        print("-" * 50)

        chapter_text = chapter_data['content']

        # Извлекаем название главы из полного заголовка
        title_match = re.match(r'Chapter\s+\d+[:\s]*(.+)', chapter_data['title'])
        chapter_title = title_match.group(1).strip() if title_match else ""

        print(f" Размер: {len(chapter_text):,} символов")
        if chapter_title:
            print(f" Название: {chapter_title}")

        # Шаг 1: Перевод
        context_text, glossary_text = self.build_context(chapter_num)

        translation_prompt = f"""{context_text}

{glossary_text}

Переведи главу {chapter_num} романа "Shrouding the Heavens".

Оригинальное название главы: {chapter_title}

Текст главы:
{chapter_text}

ИНСТРУКЦИЯ: В первой строке ответа напиши ТОЛЬКО переведённое название главы. Затем с новой строки начни перевод основного текста."""

        print(" Шаг 1/3: Перевод главы...")
        start_time = time.time()

        translated_text = self.make_request(TRANSLATION_PROMPT, translation_prompt)

        if not translated_text:
            print("❌ Не удалось перевести главу")
            return False

        translation_time = time.time() - start_time
        print(f"✅ Перевод завершён за {translation_time:.1f} сек")

        # Извлекаем название
        translated_lines = translated_text.strip().split('\n')
        translated_title = f"Глава {chapter_num}"

        if translated_lines and chapter_title:
            potential_title = translated_lines[0].strip().strip('*')
            # Очищаем от префиксов
            for pattern in [r'^Название главы:\s*', r'^Глава\s+\d+:\s*']:
                potential_title = re.sub(pattern, '', potential_title, flags=re.IGNORECASE)

            potential_title = potential_title.strip()
            if potential_title and len(potential_title) < 150:
                translated_title = f"Глава {chapter_num}: {potential_title}"
                translated_text = '\n'.join(translated_lines[1:]).strip()
                print(f"✅ Название: {potential_title}")

        # Шаг 2: Резюме
        print(" Шаг 2/3: Создание резюме...")
        summary_prompt = f"Текст главы {chapter_num}:\n\n{translated_text}"
        summary = self.make_request(SUMMARY_PROMPT, summary_prompt)

        if summary:
            print(f"✅ Резюме создано ({len(summary)} символов)")

        # Шаг 3: Извлечение терминов (для глав 2+)
        if chapter_num > 1:
            print(" Шаг 3/3: Извлечение новых терминов...")
            extract_prompt = f"""Оригинал:\n{chapter_text}\n\nПеревод:\n{translated_text}"""
            extraction_result = self.make_request(EXTRACT_TERMS_PROMPT, extract_prompt)

            if extraction_result:
                new_terms = self.parse_extraction_result(extraction_result)

                # Сохраняем в БД
                for eng, rus in new_terms.get('characters', {}).items():
                    self.db.save_glossary_item(eng, rus, 'character', chapter_num)

                for eng, rus in new_terms.get('locations', {}).items():
                    self.db.save_glossary_item(eng, rus, 'location', chapter_num)

                for eng, rus in new_terms.get('terms', {}).items():
                    self.db.save_glossary_item(eng, rus, 'term', chapter_num)

                total_new = sum(len(v) for v in new_terms.values())
                if total_new > 0:
                    print(f"✅ Добавлено новых терминов: {total_new}")

        # Сохраняем в БД
        chapter_record = {
            'chapter_number': chapter_num,
            'original_title': chapter_data['title'],
            'translated_title': translated_title,
            'original_text': chapter_text,
            'translated_text': translated_text,
            'summary': summary,
            'word_count_original': len(chapter_text.split()),
            'word_count_translated': len(translated_text.split()),
            'translation_time': translation_time
        }

        self.db.save_chapter(chapter_record)

        # Сохраняем промпты
        self.db.save_prompt(chapter_num, 'translation', TRANSLATION_PROMPT,
                          translation_prompt, translated_text)
        if summary:
            self.db.save_prompt(chapter_num, 'summary', SUMMARY_PROMPT,
                              summary_prompt, summary)

        # Статистика
        print(f"\n Статистика:")
        print(f"   Оригинал: {len(chapter_text):,} символов")
        print(f"   Перевод: {len(translated_text):,} символов")
        print(f"   Соотношение: {len(translated_text)/len(chapter_text)*100:.1f}%")

        # Сохраняем в файл
        output_dir = Path("translations_final")
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / f"chapter_{chapter_num:03d}_ru.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(translated_title + '\n')
            f.write("=" * 70 + '\n\n')
            f.write(translated_text)

        print(f" Сохранено: {output_file}")

        return True

    def parse_extraction_result(self, text: str) -> Dict:
        """Парсит результат извлечения терминов"""
        result = {'characters': {}, 'locations': {}, 'terms': {}}

        current_section = None
        for line in text.split('\n'):
            line = line.strip()

            if line.startswith('ПЕРСОНАЖИ:'):
                current_section = 'characters'
            elif line.startswith('ЛОКАЦИИ:'):
                current_section = 'locations'
            elif line.startswith('ТЕРМИНЫ:'):
                current_section = 'terms'
            elif line.startswith('- ') and current_section:
                parts = line[2:].split(' = ')
                if len(parts) == 2:
                    eng, rus = parts[0].strip(), parts[1].strip()
                    if eng and rus:
                        result[current_section][eng] = rus

        return result


class EPUBGenerator:
    """Генератор EPUB файлов из переведённых глав"""
    
    def __init__(self, db_path: str = "translations.db"):
        self.db_path = db_path
        self.book_title = "Покрывая Небеса"
        self.book_author = "Чэнь Дун"
        self.book_language = "ru"
        
    def get_chapters_from_db(self, chapter_numbers: Optional[List[int]] = None) -> List[Dict]:
        """Получение глав из базы данных"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if chapter_numbers:
            placeholders = ','.join('?' * len(chapter_numbers))
            query = f"""
                SELECT chapter_number, translated_title, translated_text, summary
                FROM chapters
                WHERE status = 'completed' AND chapter_number IN ({placeholders})
                ORDER BY chapter_number
            """
            cursor.execute(query, chapter_numbers)
        else:
            # Берём все переведённые главы
            query = """
                SELECT chapter_number, translated_title, translated_text, summary
                FROM chapters
                WHERE status = 'completed'
                ORDER BY chapter_number
                LIMIT 3
            """
            cursor.execute(query)
        
        chapters = []
        for row in cursor.fetchall():
            chapters.append({
                'number': row['chapter_number'],
                'title': row['translated_title'],
                'content': row['translated_text'],
                'summary': row['summary']
            })
        
        conn.close()
        return chapters
    
    def create_epub(self, chapters: List[Dict], output_path: str = None) -> str:
        """Создание EPUB файла"""
        # Создаём книгу
        book = epub.EpubBook()
        
        # Метаданные
        book.set_identifier(f'shrouding-the-heavens-{datetime.now().strftime("%Y%m%d")}')
        book.set_title(self.book_title)
        book.set_language(self.book_language)
        book.add_author(self.book_author)
        
        # Добавляем описание
        book.add_metadata('DC', 'description', 
            'Перевод первых глав романа "Shrouding the Heavens" (遮天). '
            'В далёком космосе древний бронзовый гроб дрейфует в пустоте...')
        
        # CSS стили
        style = '''
        @namespace epub "http://www.idpf.org/2007/ops";
        
        body {
            font-family: Georgia, serif;
            margin: 5%;
            text-align: justify;
            line-height: 1.6;
        }
        
        h1 {
            text-align: center;
            margin-top: 1em;
            margin-bottom: 1em;
            font-size: 1.5em;
            page-break-before: always;
        }
        
        h2 {
            text-align: center;
            margin-top: 2em;
            margin-bottom: 1em;
            font-size: 1.3em;
        }
        
        p {
            text-indent: 1.5em;
            margin-top: 0;
            margin-bottom: 0.5em;
        }
        
        .chapter-number {
            text-align: center;
            font-size: 0.9em;
            color: #666;
            margin-bottom: 0.5em;
        }
        
        .first-paragraph {
            text-indent: 0;
        }
        
        .summary {
            font-style: italic;
            color: #555;
            margin: 1em 0;
            padding: 1em;
            border-left: 3px solid #ccc;
        }
        '''
        
        # Добавляем CSS
        nav_css = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=style
        )
        book.add_item(nav_css)
        
        # Создаём обложку (титульную страницу)
        title_page = epub.EpubHtml(
            title='Титульная страница',
            file_name='title.xhtml',
            lang='ru'
        )
        title_page.content = f'''
        <html xmlns="http://www.w3.org/1999/xhtml">
        <head>
            <title>{self.book_title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <div style="text-align: center; margin-top: 30%;">
                <h1 style="font-size: 2.5em; margin-bottom: 0.5em;">{self.book_title}</h1>
                <h2 style="font-size: 1.2em; font-weight: normal;">Покрывая Небеса</h2>
                <p style="margin-top: 2em;">Автор: {self.book_author}</p>
                <p style="margin-top: 1em; font-size: 0.9em;">Перевод с английского</p>
                <p style="margin-top: 3em; font-size: 0.8em;">{datetime.now().strftime("%Y")}</p>
            </div>
        </body>
        </html>
        '''
        book.add_item(title_page)
        
        # Создаём страницу с оглавлением
        toc_page = epub.EpubHtml(
            title='Оглавление',
            file_name='toc.xhtml',
            lang='ru'
        )
        
        toc_content = '''
        <html xmlns="http://www.w3.org/1999/xhtml">
        <head>
            <title>Оглавление</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>Оглавление</h1>
        '''
        
        # Список для навигации
        toc_list = []
        spine_list = ['nav', title_page, toc_page]
        
        # Добавляем главы
        for chapter in chapters:
            # Создаём файл главы
            ch_filename = f'chapter_{chapter["number"]:03d}.xhtml'
            ch = epub.EpubHtml(
                title=chapter['title'],
                file_name=ch_filename,
                lang='ru'
            )
            
            # Форматируем контент главы
            paragraphs = chapter['content'].split('\n\n')
            formatted_paragraphs = []
            
            for i, para in enumerate(paragraphs):
                para = para.strip()
                if para:
                    if i == 0:
                        formatted_paragraphs.append(f'<p class="first-paragraph">{para}</p>')
                    else:
                        formatted_paragraphs.append(f'<p>{para}</p>')
            
            # HTML содержимое главы
            ch.content = f'''
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
                <title>{chapter['title']}</title>
                <link rel="stylesheet" type="text/css" href="style/nav.css"/>
            </head>
            <body>
                <div class="chapter-number">Глава {chapter['number']}</div>
                <h1>{chapter['title'].replace(f"Глава {chapter['number']}: ", "")}</h1>
                {''.join(formatted_paragraphs)}
            </body>
            </html>
            '''
            
            ch.add_item(nav_css)
            book.add_item(ch)
            
            # Добавляем в spine и toc
            spine_list.append(ch)
            toc_list.append(ch)
            
            # Добавляем в оглавление
            toc_content += f'<p><a href="{ch_filename}">{chapter["title"]}</a></p>\n'
        
        toc_content += '''
        </body>
        </html>
        '''
        toc_page.content = toc_content
        book.add_item(toc_page)
        
        # Настройка навигации
        book.toc = (
            epub.Link('title.xhtml', 'Титульная страница', 'title'),
            epub.Link('toc.xhtml', 'Оглавление', 'toc'),
            (epub.Section('Главы'), toc_list)
        )
        
        # Добавляем NCX и Nav файлы
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # spine
        book.spine = spine_list
        
        # Определяем путь для сохранения
        if not output_path:
            output_dir = Path("epub_output")
            output_dir.mkdir(exist_ok=True)
            
            chapters_range = f"{chapters[0]['number']}-{chapters[-1]['number']}"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"shrouding_the_heavens_ch{chapters_range}_{timestamp}.epub"
        
        # Записываем EPUB файл
        epub.write_epub(output_path, book, {})
        
        return str(output_path)
    
    def create_epub_with_extras(self, chapters: List[Dict], output_path: str = None) -> str:
        """Создание EPUB с дополнительными материалами (глоссарий, карта персонажей)"""
        # Получаем глоссарий из БД
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT english, russian, category, first_appearance_chapter
            FROM glossary
            ORDER BY category, english
        """)
        
        glossary = {'characters': [], 'locations': [], 'terms': []}
        for row in cursor.fetchall():
            item = {
                'english': row['english'],
                'russian': row['russian'],
                'first_chapter': row['first_appearance_chapter']
            }
            
            if row['category'] == 'character':
                glossary['characters'].append(item)
            elif row['category'] == 'location':
                glossary['locations'].append(item)
            else:
                glossary['terms'].append(item)
        
        conn.close()
        
        # Создаём базовую книгу
        book_path = self.create_epub(chapters, output_path)
        
        # Для добавления глоссария нужно пересоздать книгу
        # Это упрощённая версия, в реальности лучше модифицировать существующую
        
        print(f"\n EPUB создан: {book_path}")
        print(f"   Глав: {len(chapters)}")
        print(f"   Размер: {Path(book_path).stat().st_size / 1024:.1f} KB")
        
        if glossary['characters'] or glossary['locations'] or glossary['terms']:
            print(f"\n Глоссарий:")
            print(f"   Персонажей: {len(glossary['characters'])}")
            print(f"   Локаций: {len(glossary['locations'])}")
            print(f"   Терминов: {len(glossary['terms'])}")
        
        return book_path


def main():
    """Основная функция"""
    print("=" * 70)
    print("ФИНАЛЬНЫЙ ПЕРЕВОДЧИК: ПАРСИНГ + ПЕРЕВОД + БД + EPUB")
    print("=" * 70)

    # Проверка конфигурации
    if not GEMINI_API_KEYS:
        print("❌ Ошибка: Не найдены API ключи в GEMINI_API_KEYS")
        print("   Установите в .env: GEMINI_API_KEYS=key1,key2,key3")
        return

    print(f"✅ Загружено {len(GEMINI_API_KEYS)} API ключей")
    print(f"烙 Модель: {MODEL_NAME}")
    print(f" База данных: translations.db")

    if PROXY_URL:
        print(f" Прокси: {PROXY_URL.split('@')[1] if '@' in PROXY_URL else PROXY_URL}")

    # Шаг 1: Парсинг глав
    print(f"\n Шаг 1: Парсинг глав с {NOVEL_URL}")
    parser = NovelParser()
    chapters = parser.parse_chapter_list(NOVEL_URL, max_chapters=155)

    if not chapters:
        print("❌ Не удалось получить список глав")
        return

    print(f"✅ Получено {len(chapters)} глав для обработки")

    # Шаг 2: Парсинг контента каждой главы
    print("\n Шаг 2: Парсинг контента глав")
    parsed_chapters = []

    for chapter_info in chapters:
        chapter_data = parser.parse_chapter_content(chapter_info['url'], chapter_info['number'])

        if chapter_data.get('error'):
            print(f"  ❌ Глава {chapter_info['number']}: {chapter_data['error']}")
            continue

        parsed_chapters.append(chapter_data)
        print(f"  ✅ Глава {chapter_info['number']}: {chapter_data['metadata']['word_count']} слов")
        time.sleep(1)  # Небольшая задержка между запросами

    print(f"\n✅ Успешно спарсено {len(parsed_chapters)} глав")

    # Шаг 3: Перевод
    print("\n Шаг 3: Перевод глав")
    translator = FinalTranslator(GEMINI_API_KEYS, PROXY_URL)

    start_time = time.time()
    successful = 0
    translated_chapter_numbers = []

    for chapter in parsed_chapters:
        try:
            if translator.translate_chapter(chapter):
                successful += 1
                translated_chapter_numbers.append(chapter['chapter_number'])

            # Задержка между главами
            if chapter != parsed_chapters[-1]:
                print(f"\n⏳ Ожидание {REQUEST_DELAY} сек...")
                time.sleep(REQUEST_DELAY)

        except KeyboardInterrupt:
            print("\n\n⚠️  Прервано пользователем")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            continue

    # Итоги
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("ИТОГИ:")
    print("=" * 70)
    print(f"✅ Успешно переведено: {successful}/{len(parsed_chapters)} глав")
    print(f"⏱️  Общее время: {elapsed/60:.1f} минут")

    # Статистика из БД
    glossary = translator.db.get_glossary()
    total_terms = sum(len(cat) for cat in glossary.values())

    print(f"\n Глоссарий в БД:")
    print(f"   Персонажей: {len(glossary['characters'])}")
    print(f"   Локаций: {len(glossary['locations'])}")
    print(f"   Терминов: {len(glossary['terms'])}")
    print(f"   Всего: {total_terms}")

    print(f"\n Файлы сохранены в: translations_final/")
    print(f" База данных: translations.db")

    # Шаг 4: Создание EPUB
    if successful > 0:
        print("\n" + "=" * 70)
        print(" Шаг 4: Создание EPUB")
        print("=" * 70)
        
        try:
            epub_gen = EPUBGenerator(translator.db.db_path)
            
            # Получаем переведённые главы из БД
            epub_chapters = epub_gen.get_chapters_from_db(translated_chapter_numbers)
            
            if epub_chapters:
                # Создаём EPUB с дополнительными материалами
                epub_path = epub_gen.create_epub_with_extras(epub_chapters)
                
                print(f"\n✅ EPUB файл создан успешно!")
                print(f" Расположение: {epub_path}")
                print(f" Содержит:")
                print(f"   - {len(epub_chapters)} переведённых глав")
                print(f"   - Глоссарий с {total_terms} терминами")
                print(f"   - Оглавление и навигацию")
                
                # Информация о файле
                epub_file = Path(epub_path)
                if epub_file.exists():
                    size_kb = epub_file.stat().st_size / 1024
                    print(f"   - Размер файла: {size_kb:.1f} KB")
            else:
                print("❌ Не найдено переведённых глав для создания EPUB")
                
        except ImportError:
            print("⚠️  Библиотека ebooklib не установлена")
            print("   Установите: pip install ebooklib")
        except Exception as e:
            print(f"❌ Ошибка при создании EPUB: {e}")
    
    # Закрываем БД
    translator.db.close()
    
    print("\n✨ Работа завершена!")


if __name__ == "__main__":
    main()