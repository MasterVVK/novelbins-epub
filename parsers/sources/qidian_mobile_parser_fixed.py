#!/usr/bin/env python3
"""
Исправленный парсер Qidian на основе мобильной версии
Обрабатывает сжатые HTTP ответы правильно
"""
import requests
import json
import time
import re
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class QidianChapter:
    """Модель главы Qidian"""
    number: int
    title: str
    content: str
    url: str
    chapter_id: str
    word_count: int


@dataclass
class QidianBook:
    """Модель книги Qidian"""
    book_id: str
    title: str
    author: str
    status: str
    genre: str
    description: str
    total_chapters: int
    chapters: List[QidianChapter] = None


class QidianMobileParserFixed:
    """Исправленный парсер мобильной версии Qidian"""
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://m.qidian.com"
        
        # Настройка заголовков для мобильной версии
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'identity',  # Отключаем сжатие для отладки
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })
    
    def _get_page_content(self, url: str, description: str = "") -> Optional[str]:
        """Получение и проверка HTML контента страницы"""
        try:
            print(f"🌐 Запрос {description}: {url}")
            response = self.session.get(url, timeout=15)
            print(f"   Статус: {response.status_code}")
            print(f"   Размер: {len(response.content)} байт")
            print(f"   Content-Type: {response.headers.get('Content-Type', 'Неизвестно')}")
            print(f"   Content-Encoding: {response.headers.get('Content-Encoding', 'Нет')}")
            
            if response.status_code != 200:
                print(f"❌ HTTP ошибка: {response.status_code}")
                return None
            
            # Получаем содержимое
            html_content = response.text
            print(f"   Декодированный размер: {len(html_content)} символов")
            
            # Проверяем, что это валидный HTML
            if not html_content or len(html_content) < 500:
                print(f"❌ Слишком короткий ответ: {len(html_content)} символов")
                return None
            
            # Проверяем, что начинается как HTML
            content_start = html_content.strip()[:100]
            if not (content_start.startswith('<!DOCTYPE') or content_start.startswith('<html')):
                print(f"❌ Ответ не является HTML. Начало: {content_start}")
                return None
            
            print(f"✅ HTML контент получен успешно")
            return html_content
            
        except Exception as e:
            print(f"❌ Ошибка при получении страницы: {e}")
            return None
    
    def get_book_info(self, book_id: str) -> Optional[QidianBook]:
        """Получение информации о книге"""
        print(f"📖 Получение информации о книге {book_id}...")
        
        url = f"{self.base_url}/book/{book_id}"
        html_content = self._get_page_content(url, "информации о книге")
        
        if not html_content:
            return None
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Сохраняем HTML для отладки
            debug_file = f"debug_book_{book_id}_fixed.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"🔍 HTML сохранен для отладки: {debug_file}")
            
            # Извлекаем информацию о книге с различными стратегиями
            title = self._extract_title(soup)
            author = self._extract_author(soup)
            genre = self._extract_genre(soup)
            status = self._extract_status(soup, html_content)
            description = self._extract_description(soup)
            
            print(f"✅ Найдена книга: {title}")
            print(f"   Автор: {author}")
            print(f"   Жанр: {genre}")
            print(f"   Статус: {status}")
            
            return QidianBook(
                book_id=book_id,
                title=title,
                author=author,
                status=status,
                genre=genre,
                description=description,
                total_chapters=0  # Будет определено позже
            )
            
        except Exception as e:
            print(f"❌ Ошибка при обработке информации о книге: {e}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлечение названия книги с несколькими стратегиями"""
        selectors = [
            'h1.detail__header-detail__title',
            'h1[class*="title"]',
            'h1',
            '.book-title',
            '.title',
            '[class*="book-name"]',
            'title'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text().strip()
                if text and len(text) > 1 and not text.startswith('《') and '小说' not in text:
                    if selector == 'title':
                        # Из title тега извлекаем только название книги
                        text = text.split('》')[0].replace('《', '').split('小说')[0].strip()
                    print(f"   Найдено название ({selector}): {text}")
                    return text
        
        return "Неизвестно"
    
    def _extract_author(self, soup: BeautifulSoup) -> str:
        """Извлечение автора"""
        selectors = [
            'a.detail__header-detail__author-link',
            '.detail__header-detail__author-link',
            'a[href*="author"]',
            '.author',
            '.writer',
            '[class*="author"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text().strip()
                if text and len(text) > 1:
                    # Убираем теги и символы
                    text = text.split()[0] if text else text
                    print(f"   Найден автор ({selector}): {text}")
                    return text
        
        return "Неизвестно"
    
    def _extract_genre(self, soup: BeautifulSoup) -> str:
        """Извлечение жанра"""
        selectors = [
            'a.detail__header-detail__category',
            '.detail__header-detail__category',
            '.category',
            '.genre',
            '[class*="category"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text().strip()
                if text and len(text) > 1:
                    print(f"   Найден жанр ({selector}): {text}")
                    return text
        
        return "Неизвестно"
    
    def _extract_status(self, soup: BeautifulSoup, html_content: str) -> str:
        """Извлечение статуса книги"""
        # Проверяем в HTML напрямую
        if "完本" in html_content:
            return "完本"
        elif "连载中" in html_content:
            return "连载中"
        
        # Проверяем через селекторы
        status_selectors = [
            '.detail__header-detail__line',
            '.status',
            '[class*="status"]'
        ]
        
        for selector in status_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text()
                if "完本" in text:
                    return "完本"
                elif "连载" in text:
                    return "连载中"
        
        return "连载中"  # По умолчанию
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Извлечение описания"""
        selectors = [
            'p.detail__summary__content',
            '.detail__summary__content',
            '.summary',
            '.description', 
            '[class*="summary"]',
            '[class*="intro"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text().strip()
                if text and len(text) > 10:
                    print(f"   Найдено описание ({selector}): {text[:50]}...")
                    return text
        
        return ""
    
    def get_chapter_list(self, book_id: str) -> List[Dict]:
        """Получение списка глав"""
        print(f"📑 Получение списка глав для книги {book_id}...")
        
        catalog_url = f"{self.base_url}/book/{book_id}/catalog/"
        html_content = self._get_page_content(catalog_url, "каталога глав")
        
        if not html_content:
            return []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Сохраняем для отладки
            debug_file = f"debug_catalog_{book_id}_fixed.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"🔍 HTML каталога сохранен: {debug_file}")
            
            # Ищем ссылки на главы разными способами
            chapters = []
            
            # Способ 1: по классу chapter-link
            chapter_links = soup.find_all('a', class_='chapter-link')
            print(f"   Найдено по классу 'chapter-link': {len(chapter_links)}")
            
            # Способ 2: по href паттерну
            if not chapter_links:
                chapter_links = soup.find_all('a', href=re.compile(r'/chapter/\d+/\d+/'))
                print(f"   Найдено по href паттерну: {len(chapter_links)}")
            
            # Способ 3: все ссылки со словом "chapter"
            if not chapter_links:
                chapter_links = soup.find_all('a', href=re.compile(r'chapter'))
                print(f"   Найдено ссылок с 'chapter': {len(chapter_links)}")
            
            # Обрабатываем найденные ссылки
            for i, link in enumerate(chapter_links):
                href = link.get('href', '')
                title = link.get_text().strip()
                
                if not href or not title:
                    continue
                
                # Извлекаем ID главы из URL
                chapter_id = ""
                match = re.search(r'/chapter/(\d+)/(\d+)/', href)
                if match:
                    chapter_id = match.group(2)
                
                # Формируем полный URL
                if href.startswith('//'):
                    full_url = f"https:{href}"
                elif href.startswith('/'):
                    full_url = f"{self.base_url}{href}"
                else:
                    full_url = href
                
                # Исправляем дублирование домена
                full_url = full_url.replace('//m.qidian.com//m.qidian.com/', '//m.qidian.com/')
                full_url = full_url.replace('https://m.qidian.com//m.qidian.com/', 'https://m.qidian.com/')
                
                chapters.append({
                    'number': i + 1,
                    'title': title,
                    'url': full_url,
                    'chapter_id': chapter_id or str(i + 1)
                })
            
            print(f"✅ Найдено глав: {len(chapters)}")
            if chapters:
                print("📖 Первые найденные главы:")
                for ch in chapters[:3]:
                    print(f"   {ch['number']}. {ch['title'][:40]} → {ch['url']}")
            
            return chapters
            
        except Exception as e:
            print(f"❌ Ошибка при получении списка глав: {e}")
            return []
    
    def get_chapter_content(self, chapter_url: str, chapter_number: int, title: str) -> Optional[QidianChapter]:
        """Получение содержимого главы"""
        print(f"📄 Загрузка главы {chapter_number}: {title[:50]}...")
        
        html_content = self._get_page_content(chapter_url, f"главы {chapter_number}")
        
        if not html_content:
            return None
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Ищем контент главы с расширенными селекторами
            content_selectors = [
                '#reader-content .content',    # Основной контент
                '#reader-content',             # Контейнер читалки
                '.chapter-content',            # Контент главы
                '.content main',               # Основная область
                'main.content',                # Главная область контента
                '.print .content',             # Область печати
                '.reader-content',             # Читалка
                '[class*="content"]'           # Любой класс с content
            ]
            
            content_elem = None
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    print(f"   Контент найден через селектор: {selector}")
                    break
            
            if not content_elem:
                print("❌ Контент главы не найден")
                return None
            
            # Извлекаем параграфы
            paragraphs = []
            p_elements = content_elem.find_all('p')
            
            for p in p_elements:
                text = p.get_text().strip()
                if text and len(text) > 10:  # Фильтруем короткие строки
                    paragraphs.append(text)
            
            if not paragraphs:
                # Если параграфы не найдены, берем весь текст
                full_text = content_elem.get_text()
                lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                paragraphs = [line for line in lines if len(line) > 20]
            
            if not paragraphs:
                print("❌ Текст главы не найден")
                return None
            
            content = '\n\n'.join(paragraphs)
            word_count = len(content)
            
            # Извлекаем chapter_id из URL
            chapter_id_match = re.search(r'/chapter/\d+/(\d+)/', chapter_url)
            chapter_id = chapter_id_match.group(1) if chapter_id_match else str(chapter_number)
            
            print(f"✅ Получено {len(paragraphs)} параграфов, {word_count} символов")
            
            return QidianChapter(
                number=chapter_number,
                title=title,
                content=content,
                url=chapter_url,
                chapter_id=chapter_id,
                word_count=word_count
            )
            
        except Exception as e:
            print(f"❌ Ошибка при загрузке главы: {e}")
            return None
    
    def parse_book(self, book_id: str, max_chapters: int = 10) -> Optional[QidianBook]:
        """Полный парсинг книги"""
        print(f"🚀 Начинаем парсинг книги {book_id}")
        print("=" * 60)
        
        # Получаем информацию о книге
        book = self.get_book_info(book_id)
        if not book:
            return None
        
        # Получаем список глав
        chapter_list = self.get_chapter_list(book_id)
        if not chapter_list:
            print("❌ Не удалось получить список глав")
            return book
        
        book.total_chapters = len(chapter_list)
        
        # Ограничиваем количество глав
        chapters_to_parse = chapter_list[:max_chapters]
        print(f"\n📚 Будет загружено {len(chapters_to_parse)} из {len(chapter_list)} глав")
        
        # Парсим главы
        parsed_chapters = []
        for i, chapter_info in enumerate(chapters_to_parse):
            print(f"\n[{i+1}/{len(chapters_to_parse)}]")
            
            chapter = self.get_chapter_content(
                chapter_info['url'],
                chapter_info['number'],
                chapter_info['title']
            )
            
            if chapter:
                parsed_chapters.append(chapter)
                
                # Сохраняем главу в файл
                self.save_chapter_to_file(chapter, book.title)
            
            # Пауза между запросами
            if i < len(chapters_to_parse) - 1:
                time.sleep(2)  # Увеличиваем паузу для стабильности
        
        book.chapters = parsed_chapters
        
        print(f"\n✅ Парсинг завершен!")
        print(f"📊 Успешно загружено: {len(parsed_chapters)}/{len(chapters_to_parse)} глав")
        
        return book
    
    def save_chapter_to_file(self, chapter: QidianChapter, book_title: str):
        """Сохранение главы в файл"""
        # Создаем папку для книги
        safe_title = re.sub(r'[^\w\s-]', '', book_title)
        output_dir = Path(f"qidian_parsed/{safe_title}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем главу
        filename = f"chapter_{chapter.number:03d}_{chapter.chapter_id}.txt"
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{chapter.title}\n")
            f.write("=" * 60 + "\n\n")
            f.write(chapter.content)
        
        print(f"💾 Сохранено: {filepath}")
    
    def save_book_info(self, book: QidianBook):
        """Сохранение информации о книге в JSON"""
        safe_title = re.sub(r'[^\w\s-]', '', book.title)
        output_dir = Path(f"qidian_parsed/{safe_title}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        book_info = {
            'book_id': book.book_id,
            'title': book.title,
            'author': book.author,
            'status': book.status,
            'genre': book.genre,
            'description': book.description,
            'total_chapters': book.total_chapters,
            'parsed_chapters': len(book.chapters) if book.chapters else 0,
            'chapters': []
        }
        
        if book.chapters:
            for chapter in book.chapters:
                book_info['chapters'].append({
                    'number': chapter.number,
                    'title': chapter.title,
                    'chapter_id': chapter.chapter_id,
                    'url': chapter.url,
                    'word_count': chapter.word_count
                })
        
        filepath = output_dir / "book_info.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(book_info, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Информация о книге сохранена: {filepath}")


def main():
    """Основная функция для тестирования парсера"""
    print("🚀 Qidian Mobile Parser (Fixed) - Тестирование")
    print("=" * 70)
    
    parser = QidianMobileParserFixed()
    
    # Примеры книг для тестирования
    test_books = [
        ("1209977", "斗破苍穹 (Battle Through the Heavens)"),
        ("1010868264", "诡秘之主 (Lord of the Mysteries)"),
    ]
    
    print("Доступные книги для тестирования:")
    for i, (book_id, title) in enumerate(test_books, 1):
        print(f"{i}. {title} (ID: {book_id})")
    
    # Для автоматического тестирования используем первую книгу
    book_id = test_books[0][0]
    max_chapters = 2  # Ограничиваем для тестирования
    
    print(f"\n🎯 Тестируем книгу ID: {book_id}")
    print(f"📊 Максимум глав: {max_chapters}")
    
    # Парсим книгу
    book = parser.parse_book(book_id, max_chapters)
    
    if book:
        # Сохраняем информацию о книге
        parser.save_book_info(book)
        
        print(f"\n" + "=" * 70)
        print("📋 ИТОГИ ПАРСИНГА")
        print("=" * 70)
        print(f"📖 Книга: {book.title}")
        print(f"✍️ Автор: {book.author}")
        print(f"📊 Статус: {book.status}")
        print(f"🏷️ Жанр: {book.genre}")
        print(f"📚 Всего глав: {book.total_chapters}")
        print(f"✅ Загружено глав: {len(book.chapters) if book.chapters else 0}")
        
        if book.chapters:
            print(f"\n📝 Загруженные главы:")
            for chapter in book.chapters:
                print(f"   {chapter.number}. {chapter.title} ({chapter.word_count} символов)")
        
        safe_title = re.sub(r'[^\w\s-]', '', book.title)
        print(f"\n💾 Файлы сохранены в папке: qidian_parsed/{safe_title}/")
        
    else:
        print("❌ Парсинг не удался")


if __name__ == "__main__":
    main()