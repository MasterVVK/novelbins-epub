"""
1_parser_selenium.py - Парсер с поддержкой JavaScript
"""
import time
from pathlib import Path
from typing import List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import re

from models import Chapter, ParserConfig
from database import DatabaseManager


class SeleniumNovelParser:
    """Парсер с поддержкой JavaScript"""

    def __init__(self, config: ParserConfig):
        self.config = config

        # Настройки Chrome
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Без GUI
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

    def extract_chapter_number(self, url: str) -> int:
        """Извлечение номера главы из URL"""
        match = re.search(r'/chapter/(\d+)', url)
        return int(match.group(1)) if match else 0

    def parse_all_chapter_links(self) -> List[dict]:
        """Получение ВСЕХ ссылок на главы"""
        print(f" Загрузка страницы новеллы...")
        self.driver.get(self.config.novel_url)

        # Ждём загрузки вкладок
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.nav-tabs a.ch')))

        # Находим все вкладки
        tabs = self.driver.find_elements(By.CSS_SELECTOR, 'ul.nav-tabs a.ch')
        print(f"✅ Найдено вкладок: {len(tabs)}")

        all_chapters = []

        # Проходим по каждой вкладке
        for i, tab in enumerate(tabs):
            tab_text = tab.text
            print(f"\n Загрузка вкладки {i+1}/{len(tabs)}: {tab_text}")

            # Кликаем на вкладку
            tab.click()
            time.sleep(1)  # Ждём загрузки контента

            # Находим все ссылки на главы в активной вкладке
            chapter_links = self.driver.find_elements(By.CSS_SELECTOR, '#chapter-content a[href*="/chapter/"]')

            new_chapters = 0
            for link in chapter_links:
                href = link.get_attribute('href')
                title = link.text
                chapter_num = self.extract_chapter_number(href)

                if chapter_num > 0:
                    # Проверяем дубликаты
                    if not any(ch['number'] == chapter_num for ch in all_chapters):
                        all_chapters.append({
                            'url': href,
                            'title': title,
                            'number': chapter_num
                        })
                        new_chapters += 1

            print(f"✅ Найдено {len(chapter_links)} ссылок, новых глав: {new_chapters}")

        # Сортируем по номеру
        all_chapters.sort(key=lambda x: x['number'])

        print(f"\n✅ Всего найдено глав: {len(all_chapters)}")
        return all_chapters

    def parse_chapter_content(self, chapter_url: str, chapter_number: int) -> Optional[Chapter]:
        """Парсинг содержимого главы"""
        print(f" Загрузка главы {chapter_number}: {chapter_url}")
        self.driver.get(chapter_url)

        # Ждём загрузки контента
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.page-content-wrapper')))
        except:
            print("❌ Контент не загрузился")
            return None

        # Заголовок
        title = f"Chapter {chapter_number}"
        page_title = self.driver.title
        if page_title:
            match = re.search(r'Chapter\s*\d+[:\s]*[^-|]+', page_title)
            if match:
                title = match.group(0).strip()

        # Контент
        content_div = self.driver.find_element(By.CSS_SELECTOR, 'div.page-content-wrapper')

        # Удаляем лишнее через JavaScript
        self.driver.execute_script("""
            var elements = document.querySelectorAll('script, style, nav, button, .adsbygoogle');
            elements.forEach(function(el) { el.remove(); });
        """)

        # Извлекаем параграфы
        paragraphs = []
        p_elements = content_div.find_elements(By.TAG_NAME, 'p')

        for p in p_elements:
            text = p.text.strip()
            if text and len(text) > 30 and not text.startswith('Chapter'):
                paragraphs.append(text)

        # Если мало параграфов, берём весь текст
        if len(paragraphs) < 5:
            text = content_div.text
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
    parser.add_argument('-n', '--chapters', type=int, default=1821,
                       help='Количество глав для парсинга')
    parser.add_argument('-f', '--force', action='store_true',
                       help='Перепарсить все главы')
    args = parser.parse_args()

    print("=" * 70)
    print("ПАРСЕР ГЛАВ (Selenium)")
    print("=" * 70)

    config = ParserConfig(max_chapters=args.chapters)
    novel_parser = SeleniumNovelParser(config)
    db = DatabaseManager()
    output_dir = Path("parsed_chapters")

    try:
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

    finally:
        db.close()
        novel_parser.driver.quit()


if __name__ == "__main__":
    main()