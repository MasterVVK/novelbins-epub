import os
import json
import time
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import httpx
from httpx_socks import SyncProxyTransport
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import re

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
    """Парсер для novelbins.com"""

    def __init__(self):
        self.base_url = "https://novelbins.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get_page(self, url: str) -> Optional[str]:
        """Получение HTML страницы"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Ошибка при загрузке {url}: {e}")
            return None

    def parse_chapter_list(self, novel_url: str, max_chapters: int = 3) -> List[Dict[str, str]]:
        """Получение списка ссылок на главы с учётом пагинации"""
        print(f" Парсинг списка глав...")

        all_chapters = []
        page_num = 1
        base_url = novel_url.rstrip('/')

        while len(all_chapters) < max_chapters:
            # Формируем URL страницы
            if page_num == 1:
                page_url = base_url
            else:
                page_url = f"{base_url}/#{page_num}"

            html = self.get_page(page_url)
            if not html:
                break

            soup = BeautifulSoup(html, 'html.parser')

            # Контейнер с главами
            chapters_container = soup.find('div', class_='chapters')

            if chapters_container:
                links = chapters_container.find_all('a', href=lambda x: x and '/chapter/' in x)

                for link in links:
                    if len(all_chapters) >= max_chapters:
                        break

                    href = link.get('href', '')
                    title = link.text.strip()

                    # Извлекаем номер главы
                    match = re.search(r'/chapter/(\d+)', href)
                    if match:
                        chapter_num = int(match.group(1))

                        if href and not href.startswith('http'):
                            href = self.base_url + href

                        # Проверяем, что это не дубликат
                        if not any(ch['number'] == chapter_num for ch in all_chapters):
                            all_chapters.append({
                                'url': href,
                                'title': title,
                                'number': chapter_num
                            })

            # Проверяем, есть ли ещё страницы
            if len(links) == 0 or len(all_chapters) >= max_chapters:
                break

            page_num += 1

            # Защита от бесконечного цикла
            if page_num > 10:
                break

        # Сортируем по номеру главы
        all_chapters.sort(key=lambda x: x['number'])

        # Берём нужное количество
        chapter_links = all_chapters[:max_chapters]

        print(f"✅ Найдено {len(all_chapters)} глав, выбрано первые {len(chapter_links)}")

        # Показываем что нашли
        for ch in chapter_links[:5]:  # Показываем первые 5
            print(f"   Глава {ch['number']}: {ch['title']}")

        return chapter_links

    def parse_chapter_content(self, chapter_url: str) -> Dict[str, str]:
        """Парсинг содержимого главы"""
        html = self.get_page(chapter_url)

        if not html:
            return {'error': 'Failed to load chapter'}

        soup = BeautifulSoup(html, 'html.parser')

        # Извлекаем номер главы из URL для правильного заголовка
        chapter_num_match = re.search(r'/chapter/(\d+)', chapter_url)
        chapter_num = chapter_num_match.group(1) if chapter_num_match else ""

        # Ищем заголовок главы в разных местах
        title = f"Chapter {chapter_num}"

        # Попробуем найти в мета-тегах или title страницы
        page_title = soup.find('title')
        if page_title:
            # Обычно формат: "Chapter X: Title - Shrouding the Heavens"
            title_text = page_title.text.strip()
            # Извлекаем часть до " - Shrouding"
            if " - Shrouding" in title_text:
                title = title_text.split(" - Shrouding")[0].strip()
            elif "Chapter" in title_text:
                title = title_text.strip()

        # Также проверим h1 или другие заголовки на странице
        for tag in ['h1', 'h2', 'h3']:
            heading = soup.find(tag)
            if heading and "Chapter" in heading.text:
                potential_title = heading.text.strip()
                if len(potential_title) < 200:  # Разумная длина для заголовка
                    title = potential_title
                    break

        print(f"   Найден заголовок: {title}")

        # Поиск контента
        content_elem = soup.find('div', class_='page-content-wrapper')

        if not content_elem:
            # Альтернативный поиск
            for selector in ['div.content', 'div#content', 'article', 'div.chapter-content']:
                content_elem = soup.select_one(selector)
                if content_elem:
                    break

        if content_elem:
            # Удаление ненужных элементов
            for tag in content_elem.find_all(['script', 'style', 'nav', 'button', 'ins', 'iframe']):
                tag.decompose()

            # Извлечение текстовых узлов
            text_nodes = []
            for elem in content_elem.descendants:
                if isinstance(elem, str):
                    text = elem.strip()
                    if text and len(text) > 50:
                        # Фильтруем навигационные элементы
                        if not any(skip in text.lower() for skip in ['next chapter', 'previous chapter', 'advertisement']):
                            text_nodes.append(text)

            # Объединение в параграфы
            content = '\n\n'.join(text_nodes)

            return {
                'title': title,
                'content': content,
                'error': None
            }

        return {'error': 'Content not found'}


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

    def translate_chapter(self, chapter_data: Dict, chapter_num: int) -> bool:
        """Перевод главы с сохранением в БД"""
        print(f"\n Глава {chapter_num}: {chapter_data['title']}")
        print("-" * 50)

        chapter_text = chapter_data['content']

        # Извлекаем название главы из полного заголовка
        # Формат обычно: "Chapter 1 Bronze giant coffin in the starry sky"
        title_match = re.match(r'Chapter\s+\d+\s*[:.]?\s*(.+)', chapter_data['title'])
        chapter_title = title_match.group(1).strip() if title_match else ""

        # Если не удалось извлечь, пробуем другой формат
        if not chapter_title and "Chapter" in chapter_data['title']:
            # Убираем "Chapter X" и берём остальное
            parts = chapter_data['title'].split(maxsplit=2)
            if len(parts) > 2:
                chapter_title = parts[2]

        print(f" Размер: {len(chapter_text):,} символов")
        if chapter_title:
            print(f" Название: {chapter_title}")
        else:
            print(f"⚠️  Название главы не найдено")

        # Шаг 1: Перевод
        context_text, glossary_text = self.build_context(chapter_num)

        translation_prompt = f"""{context_text}

{glossary_text}

Переведи главу {chapter_num} романа "Shrouding the Heavens".

Оригинальное название главы: {chapter_title}

Текст главы:
{chapter_text}

ИНСТРУКЦИЯ: В первой строке ответа напиши ТОЛЬКО переведённое название главы. Затем с новой строки начни перевод основного текста."""

        print(" Шаг 1/3: Перевод главы...")
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
        print(" Шаг 2/3: Создание резюме...")
        summary_prompt = f"Текст главы {chapter_num}:\n\n{translated_text}"
        summary = self.make_request(SUMMARY_PROMPT, summary_prompt)

        if summary:
            print(f"✅ Резюме создано ({len(summary)} символов)")

        # Шаг 3: Извлечение терминов (для глав 2+)
        if chapter_num > 1:
            print(" Шаг 3/3: Извлечение новых терминов...")
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
            'word_count_original': len(chapter_text),
            'word_count_translated': len(translated_text),
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


def main():
    """Основная функция"""
    print("=" * 70)
    print("ФИНАЛЬНЫЙ ПЕРЕВОДЧИК: ПАРСИНГ + ПЕРЕВОД + БД")
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
    chapters = parser.parse_chapter_list(NOVEL_URL, max_chapters=3)

    if not chapters:
        print("❌ Не удалось получить список глав")
        return

    print(f"✅ Получено {len(chapters)} глав для обработки")

    # Шаг 2: Парсинг контента каждой главы
    print("\n Шаг 2: Парсинг контента глав")
    parsed_chapters = []

    for chapter_info in chapters:
        print(f"   Глава {chapter_info['number']}...", end='', flush=True)
        content = parser.parse_chapter_content(chapter_info['url'])

        if content.get('error'):
            print(f" ❌ {content['error']}")
            continue

        parsed_chapters.append({
            'number': chapter_info['number'],
            'title': content['title'],
            'content': content['content'],
            'url': chapter_info['url']
        })
        print(" ✅")
        time.sleep(1)  # Небольшая задержка между запросами

    print(f"\n✅ Успешно спарсено {len(parsed_chapters)} глав")

    # Шаг 3: Перевод
    print("\n Шаг 3: Перевод глав")
    translator = FinalTranslator(GEMINI_API_KEYS, PROXY_URL)

    start_time = time.time()
    successful = 0

    for chapter in parsed_chapters:
        try:
            if translator.translate_chapter(chapter, chapter['number']):
                successful += 1

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

    print(f"\n Глоссарий в БД:")
    print(f"   Персонажей: {len(glossary['characters'])}")
    print(f"   Локаций: {len(glossary['locations'])}")
    print(f"   Терминов: {len(glossary['terms'])}")
    print(f"   Всего: {total_terms}")

    print(f"\n Файлы сохранены в: translations_final/")
    print(f" База данных: translations.db")

    # Закрываем БД
    translator.db.close()


if __name__ == "__main__":
    main()