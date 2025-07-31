#!/usr/bin/env python3
"""
Реальный парсер Qidian на основе мобильной версии
Использует m.qidian.com для обхода защиты от ботов
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


class QidianMobileParser:
    """Парсер мобильной версии Qidian"""
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://m.qidian.com"
        
        # Настройка заголовков для мобильной версии
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
    
    def get_book_info(self, book_id: str) -> Optional[QidianBook]:
        """Получение информации о книге"""
        print(f"📖 Получение информации о книге {book_id}...")
        
        url = f"{self.base_url}/book/{book_id}"
        
        try:
            response = self.session.get(url, timeout=10)
            print(f"   Статус: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Ошибка загрузки страницы: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Извлекаем информацию о книге
            title_elem = soup.select_one('h1.detail__header-detail__title')
            title = title_elem.text.strip() if title_elem else "Неизвестно"
            
            author_elem = soup.select_one('a.detail__header-detail__author-link')
            author = author_elem.text.strip().split()[0] if author_elem else "Неизвестно"  # Убираем тег автора
            
            # Жанр - берем первую категорию
            genre_elems = soup.select('a.detail__header-detail__category')
            genre = genre_elems[0].text.strip() if genre_elems else "Неизвестно"
            
            # Статус (завершена/продолжается) - ищем в строках детальной информации
            status_lines = soup.select('p.detail__header-detail__line')
            status = "连载中"  # По умолчанию - продолжается
            for line in status_lines:
                line_text = line.text.strip()
                if "完本" in line_text:
                    status = "完本"
                    break
            
            # Описание
            desc_elem = soup.select_one('p.detail__summary__content')
            description = desc_elem.text.strip() if desc_elem else ""
            
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
            print(f"❌ Ошибка при получении информации о книге: {e}")
            return None
    
    def get_chapter_list(self, book_id: str) -> List[Dict]:
        """Получение списка глав"""
        print(f"📑 Получение списка глав для книги {book_id}...")
        
        catalog_url = f"{self.base_url}/book/{book_id}/catalog/"
        
        try:
            response = self.session.get(catalog_url, timeout=10)
            print(f"   Статус каталога: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Ошибка загрузки каталога: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем ссылки на главы - используем класс chapter-link
            chapter_links = soup.find_all('a', class_='chapter-link')
            if not chapter_links:
                # Запасное решение - ищем по href паттерну
                chapter_links = soup.find_all('a', href=re.compile(r'/chapter/\d+/\d+/'))
            
            chapters = []
            for i, link in enumerate(chapter_links):
                href = link.get('href')
                title = link.text.strip()
                
                # Извлекаем ID главы из URL
                match = re.search(r'/chapter/(\d+)/(\d+)/', href)
                if match:
                    book_id_from_url = match.group(1)
                    chapter_id = match.group(2)
                    
                    # Формируем полный URL
                    full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                    
                    chapters.append({
                        'number': i + 1,
                        'title': title,
                        'url': full_url,
                        'chapter_id': chapter_id
                    })
            
            print(f"✅ Найдено глав: {len(chapters)}")
            return chapters
            
        except Exception as e:
            print(f"❌ Ошибка при получении списка глав: {e}")
            return []
    
    def get_chapter_content(self, chapter_url: str, chapter_number: int, title: str) -> Optional[QidianChapter]:
        """Получение содержимого главы"""
        print(f"📄 Загрузка главы {chapter_number}: {title[:50]}...")
        
        try:
            response = self.session.get(chapter_url, timeout=10)
            print(f"   Статус: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Ошибка загрузки главы: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем контент главы - обновляем селекторы
            content_selectors = [
                '#reader-content',  # Основной контейнер с текстом
                'main.content',     # Основная область содержания
                '.content',         # Общий класс контента
                '.chapter-content', # Контент главы
                '.print .content'   # Контент в области печати
            ]
            
            content_elem = None
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
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
                time.sleep(1)  # 1 секунда между запросами
        
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
    print("🚀 Qidian Mobile Parser - Тестирование")
    print("=" * 70)
    
    parser = QidianMobileParser()
    
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
    max_chapters = 3  # Ограничиваем для тестирования
    
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
            for chapter in book.chapters[:5]:  # Показываем первые 5
                print(f"   {chapter.number}. {chapter.title} ({chapter.word_count} символов)")
        
        safe_title = re.sub(r'[^\w\s-]', '', book.title)
        print(f"\n💾 Файлы сохранены в папке: qidian_parsed/{safe_title}/")
        
    else:
        print("❌ Парсинг не удался")


if __name__ == "__main__":
    main()