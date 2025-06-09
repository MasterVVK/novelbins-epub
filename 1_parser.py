"""
1_parser.py - Простой парсер с поддержкой пагинации
"""
import time
import json
from pathlib import Path
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
import re
from dotenv import load_dotenv

from models import Chapter, ParserConfig
from database import DatabaseManager

load_dotenv()


class NovelParser:
    """Парсер для novelbins.com"""

    def __init__(self, config: ParserConfig):
        self.config = config
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
            print(f"❌ Ошибка при загрузке {url}: {e}")
            return None

    def extract_chapter_number(self, url: str) -> int:
        """Извлечение номера главы из URL"""
        match = re.search(r'/chapter/(\d+)', url)
        return int(match.group(1)) if match else 0

    def parse_all_chapter_links(self) -> List[dict]:
        """Получение ВСЕХ ссылок на главы со всех страниц"""
        all_chapters = []
        page_num = 0

        while True:
            # URL страницы: #0, #1, #2 и т.д.
            if page_num == 0:
                url = self.config.novel_url
            else:
                url = f"{self.config.novel_url}#{page_num}"

            print(f" Загрузка страницы {page_num + 1}: {url}")
            html = self.get_page(url)

            if not html:
                break

            soup = BeautifulSoup(html, 'html.parser')
            chapters_div = soup.find('div', class_='chapters')

            if not chapters_div:
                print("❌ Не найден контейнер с главами")
                break

            # Находим все ссылки на главы
            links = chapters_div.find_all('a', href=lambda x: x and '/chapter/' in x)

            if not links:
                print("✅ Больше нет глав")
                break

            # Собираем информацию о главах
            new_chapters = 0
            for link in links:
                href = link.get('href', '')
                title = link.text.strip()
                chapter_num = self.extract_chapter_number(href)

                if chapter_num > 0:
                    # Полный URL
                    if not href.startswith('http'):
                        href = self.config.base_url + href

                    # Проверяем дубликаты
                    if not any(ch['number'] == chapter_num for ch in all_chapters):
                        all_chapters.append({
                            'url': href,
                            'title': title,
                            'number': chapter_num
                        })
                        new_chapters += 1

            print(f"✅ Найдено {len(links)} ссылок, новых глав: {new_chapters}")

            # Если новых глав нет - мы дошли до конца
            if new_chapters == 0:
                break

            # Следующая страница
            page_num += 1

            # Небольшая задержка
            time.sleep(0.5)

        # Сортируем по номеру
        all_chapters.sort(key=lambda x: x['number'])

        print(f"\n✅ Всего найдено глав: {len(all_chapters)}")
        return all_chapters

    def parse_chapter_content(self, chapter_url: str, chapter_number: int) -> Optional[Chapter]:
        """Парсинг содержимого главы"""
        print(f" Загрузка главы {chapter_number}: {chapter_url}")
        html = self.get_page(chapter_url)

        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        # Заголовок главы
        title = f"Chapter {chapter_number}"
        page_title = soup.find('title')
        if page_title:
            match = re.search(r'Chapter\s*\d+[:\s]*[^-|]+', page_title.text)
            if match:
                title = match.group(0).strip()

        # Контент главы
        content_div = soup.find('div', class_='page-content-wrapper')
        if not content_div:
            # Альтернативные селекторы
            for selector in ['div.page-content', 'div.content-wrapper', 'div.chapter-content']:
                content_div = soup.select_one(selector)
                if content_div:
                    break

        if not content_div:
            print("❌ Контент не найден")
            return None

        # Удаляем лишнее
        for tag in content_div.find_all(['script', 'style', 'nav', 'button']):
            tag.decompose()

        # Извлекаем параграфы
        paragraphs = []
        for p in content_div.find_all('p'):
            text = p.text.strip()
            if text and len(text) > 30 and not text.startswith('Chapter'):
                paragraphs.append(text)

        # Если мало параграфов, берём весь текст
        if len(paragraphs) < 5:
            text = content_div.get_text(separator='\n', strip=True)
            # Разбиваем по переносам строк
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            paragraphs = [line for line in lines if len(line) > 50]

        content = '\n\n'.join(paragraphs)
        word_count = len(content.split())

        print(f"✅ Извлечено {len(paragraphs)} параграфов, {word_count} слов")

        return Chapter(
            number=chapter_number,
            original_title=title,
            original_text=content,
            url=chapter_url,
            word_count=word_count,
            paragraph_count=len(paragraphs)
        )

    def save_to_file(self, chapter: Chapter, output_dir: Path):
        """Сохранение в файл"""
        output_dir.mkdir(exist_ok=True)

        txt_file = output_dir / f"chapter_{chapter.number:03d}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"{chapter.original_title}\n")
            f.write("=" * 70 + "\n\n")
            f.write(chapter.original_text)

        print(f" Сохранено: {txt_file}")


def main():
    """Основная функция"""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--chapters', type=int, default=154,
                       help='Количество глав для парсинга')
    parser.add_argument('-f', '--force', action='store_true',
                       help='Перепарсить все главы')
    args = parser.parse_args()

    print("=" * 70)
    print("ПАРСЕР ГЛАВ")
    print("=" * 70)

    config = ParserConfig(max_chapters=args.chapters)
    novel_parser = NovelParser(config)
    db = DatabaseManager()
    output_dir = Path("parsed_chapters")

    # Получаем ВСЕ главы
    print("\n Получение списка всех глав...")
    all_chapters = novel_parser.parse_all_chapter_links()

    if not all_chapters:
        print("❌ Главы не найдены")
        return

    # Берём только нужное количество
    chapters_to_process = all_chapters[:config.max_chapters]

    # Проверяем что уже есть в БД
    if not args.force:
        existing = db.get_existing_chapter_numbers()
        chapters_to_process = [ch for ch in chapters_to_process if ch['number'] not in existing]

        if not chapters_to_process:
            print("\n✅ Все главы уже спарсены")
            return

    print(f"\n Будет спарсено глав: {len(chapters_to_process)}")

    # Парсим главы
    for i, chapter_info in enumerate(chapters_to_process, 1):
        print(f"\n[{i}/{len(chapters_to_process)}]")

        chapter = novel_parser.parse_chapter_content(
            chapter_info['url'],
            chapter_info['number']
        )

        if chapter:
            db.save_parsed_chapter(chapter)
            novel_parser.save_to_file(chapter, output_dir)

        if i < len(chapters_to_process):
            time.sleep(config.request_delay)

    print("\n✅ Готово!")
    db.close()


if __name__ == "__main__":
    main()