#!/usr/bin/env python3
"""
Парсер Qidian на основе базового класса
Оптимизированная версия для работы с мобильной версией сайта
"""
import time
import random
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import re
import sys
import os

# Добавляем путь к базовому классу
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'base'))
from base_parser import BaseParser


class QidianParser(BaseParser):
    """
    Парсер для Qidian.com (китайская платформа веб-новелл)
    Использует мобильную версию для обхода защиты от ботов
    """
    
    def __init__(self):
        super().__init__("qidian")
        
        # Специфичные заголовки для Qidian (мобильная версия)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Базовые URL
        self.mobile_base_url = "https://m.qidian.com"
        
        # Счетчики для адаптивных пауз
        self.consecutive_errors = 0
    
    def get_book_info(self, book_url: str) -> Dict:
        """
        Получить информацию о книге
        """
        book_id = self._extract_book_id(book_url)
        if not book_id:
            raise ValueError(f"Не удается извлечь ID книги из URL: {book_url}")
        
        mobile_url = f"{self.mobile_base_url}/book/{book_id}/"
        html_content = self._get_page_content(mobile_url, description=f"Информация о книге {book_id}")
        
        if not html_content:
            raise Exception(f"Не удалось получить страницу книги: {mobile_url}")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Извлекаем информацию о книге
        book_info = {
            'book_id': book_id,
            'title': self._extract_title(soup),
            'author': self._extract_author(soup),
            'status': self._extract_status(soup),
            'genre': self._extract_genre(soup),
            'description': self._extract_description(soup),
            'total_chapters': 0  # Будет определено в get_chapter_list
        }
        
        return book_info
    
    def get_chapter_list(self, book_url: str) -> List[Dict]:
        """
        Получить список глав книги
        """
        book_id = self._extract_book_id(book_url)
        if not book_id:
            raise ValueError(f"Не удается извлечь ID книги из URL: {book_url}")
        
        catalog_url = f"{self.mobile_base_url}/book/{book_id}/catalog"
        html_content = self._get_page_content(catalog_url, description=f"Каталог книги {book_id}")
        
        if not html_content:
            raise Exception(f"Не удалось получить каталог книги: {catalog_url}")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        chapters = []
        
        # Используем обновленный селектор для поиска ссылок на главы
        chapter_links = soup.select('a[href*="/chapter/"]')
        
        print(f"🔍 Найдено ссылок на главы: {len(chapter_links)}")
        
        # Фильтруем и обрабатываем главы
        all_chapters = []
        story_chapters = []
        
        # Сначала собираем все валидные главы
        for link in chapter_links:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            
            if href:
                # Преобразуем относительный URL в абсолютный
                if href.startswith('//'):
                    chapter_url = f"https:{href}"
                elif href.startswith('/'):
                    chapter_url = f"{self.mobile_base_url}{href}"
                else:
                    chapter_url = href
                
                # Извлекаем chapter_id из URL
                chapter_id = self._extract_chapter_id(chapter_url)
                
                if chapter_id:
                    chapter_info = {
                        'title': title,
                        'url': chapter_url, 
                        'chapter_id': chapter_id,
                        'is_story_chapter': self._is_story_chapter(title),
                        'word_count': 0
                    }
                    all_chapters.append(chapter_info)
        
        # Приоритизируем главы истории (начинающиеся с "第")
        story_chapters = [ch for ch in all_chapters if ch['is_story_chapter']]
        
        if not story_chapters:
            # Если нет пронумерованных глав, берем все кроме явно служебных
            print("⚠️ Пронумерованные главы не найдены, используем все доступные")
            story_chapters = [ch for ch in all_chapters if not self._is_service_chapter(ch['title'])]
        
        # Сортируем по порядковому номеру в URL (chapter_id)
        story_chapters.sort(key=lambda x: int(x['chapter_id']))
        
        # Добавляем номера глав
        for i, chapter in enumerate(story_chapters, 1):
            chapter['number'] = i
            del chapter['is_story_chapter']  # Убираем служебное поле
        
        print(f"📖 Найдено глав истории: {len(story_chapters)}")
        
        if story_chapters:
            print(f"📋 Первые 3 главы:")
            for i, ch in enumerate(story_chapters[:3]):
                print(f"   {i+1}. {ch['title']}")
        
        return story_chapters

    def _is_service_chapter(self, title: str) -> bool:
        """
        Проверяет, является ли глава служебной (уведомления автора и т.д.)
        """
        service_keywords = [
            # Служебные уведомления
            '新书', '发布', '通知', '公告', '说明', '抽奖', '活动',
            '教程', '外传', '番外', '感言', '推荐', '骗子', '冒充',
            '海量', 'iPad', '起点币', '经验', '推荐票',
            # Даты в заголовках (признак уведомлений)
            '2022-', '2023-', '2024-', '2025-',
            '作家入驻', '即更即看', '还有番外'
        ]
        
        # Проверяем на наличие служебных ключевых слов
        for keyword in service_keywords:
            if keyword in title:
                return True
        
        # Главы с очень короткими названиями часто служебные
        if len(title.strip()) < 3:
            return True
        
        # Главы содержащие только даты и время
        if '19:00' in title or '作家入驻' in title:
            return True
            
        return False

    def _is_story_chapter(self, title: str) -> bool:
        """
        Проверяет, является ли глава частью основной истории
        """
        # Главы истории обычно начинаются с "第" (глава) и содержат номер
        if title.startswith('第') and ('章' in title or '回' in title):
            return True
        
        # Дополнительные паттерны для глав истории
        story_patterns = [
            r'第\d+章',  # 第1章, 第123章 и т.д.
            r'第\d+回',  # 第1回, 第123回 и т.д.
            r'Chapter \d+',  # Английский формат
            r'Ch\.\d+',  # Сокращенный английский формат
        ]
        
        import re
        for pattern in story_patterns:
            if re.search(pattern, title):
                return True
        
        return False
    
    def get_chapter_content(self, chapter_url: str) -> Dict:
        """
        Получить содержимое главы
        """
        html_content = self._get_page_content(chapter_url, description="Содержимое главы")
        
        if not html_content:
            raise Exception(f"Не удалось получить содержимое главы: {chapter_url}")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Извлекаем заголовок главы
        title_elem = soup.select_one('h1.chapter__title, .title')
        title = title_elem.get_text(strip=True) if title_elem else "Неизвестная глава"
        
        # Извлекаем содержимое главы
        content_elem = soup.select_one('.chapter__content, .content')
        if not content_elem:
            raise Exception("Не удалось найти содержимое главы")
        
        # Очищаем содержимое от лишних элементов
        content = self._clean_chapter_content(content_elem)
        
        # Извлекаем chapter_id из URL
        chapter_id = self._extract_chapter_id(chapter_url)
        
        return {
            'title': title,
            'content': content,
            'chapter_id': chapter_id,
            'word_count': len(content)
        }
    
    def _delay_between_requests(self):
        """
        Адаптивная пауза между запросами для Qidian
        """
        # Базовая пауза
        base_delay = 1.5
        
        # Увеличиваем паузу при ошибках
        if self.consecutive_errors > 0:
            base_delay *= (1 + self.consecutive_errors * 0.5)
        
        # Случайная составляющая для имитации человека
        random_factor = random.uniform(0.2, 0.8)
        delay = base_delay + random_factor
        
        print(f"⏳ Пауза {delay:.1f}s...")
        time.sleep(delay)
    
    def _get_page_content(self, url: str, timeout: int = 10, description: str = "") -> Optional[str]:
        """
        Переопределяем метод для специфичной обработки Qidian
        """
        try:
            self.request_count += 1
            
            if description:
                print(f"🌐 {description}: {url}")
            
            response = self.session.get(url, timeout=timeout)
            
            print(f"   Статус: {response.status_code}")
            print(f"   Размер: {len(response.content):,} байт")
            
            if response.status_code == 200:
                html_content = response.text
                
                # Проверяем качество HTML для Qidian
                if (html_content and 
                    len(html_content) > 5000 and
                    html_content.strip().startswith('<') and
                    ('起点中文网' in html_content or 'qidian.com' in html_content)):
                    
                    self.success_count += 1
                    self.consecutive_errors = 0
                    print(f"✅ Качественный HTML получен")
                    return html_content
                else:
                    print("⚠️ HTML не прошел проверку качества")
                    self.consecutive_errors += 1
                    
            elif response.status_code == 202:
                print("⚠️ Сервер возвращает 202 - возможная защита от ботов")
                self.consecutive_errors += 1
                time.sleep(5)
                
            elif response.status_code == 429:
                print("⚠️ Rate limiting - слишком много запросов")
                self.consecutive_errors += 1
                time.sleep(10)
                
            else:
                print(f"❌ HTTP ошибка: {response.status_code}")
                self.consecutive_errors += 1
                
        except Exception as e:
            print(f"❌ Ошибка запроса к {url}: {e}")
            self.consecutive_errors += 1
            
        return None
    
    def _extract_book_id(self, book_url: str) -> Optional[str]:
        """
        Извлечь ID книги из URL
        """
        # Поддерживаем различные форматы URL
        patterns = [
            r'/book/(\d+)/?',
            r'qidian\.com/book/(\d+)',
            r'm\.qidian\.com/book/(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, book_url)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_chapter_id(self, chapter_url: str) -> Optional[str]:
        """
        Извлечь ID главы из URL
        """
        match = re.search(r'/chapter/\d+/(\d+)/?', chapter_url)
        return match.group(1) if match else None
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """
        Извлечь название книги
        """
        # Основной заголовок книги находится в h1
        title_elem = soup.select_one('h1')
        if title_elem:
            title = title_elem.get_text(strip=True)
            if title and title != '简介' and title != '目录':  # Исключаем служебные заголовки
                return title
        
        # Fallback селекторы
        selectors = [
            '[class*="title"]',
            '.title',
            '.book-name',
            '.book__name'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                if title and len(title) > 2 and title not in ['简介', '目录']:
                    return title
        
        return "Неизвестно"
    
    def _extract_author(self, soup: BeautifulSoup) -> str:
        """
        Извлечь автора книги
        """
        # Ищем автора по классам содержащим "author"
        author_elements = soup.select('[class*="author"]')
        for elem in author_elements:
            text = elem.get_text(strip=True)
            if text and len(text) > 1 and len(text) < 50:  # Разумная длина для имени автора
                return text
        
        # Fallback селекторы
        selectors = [
            '.book__author',
            '.book-author',
            '.author',
            '.book-info__author',
            '.writer',
            '.book-writer'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        
        return "Неизвестно"
    
    def _extract_status(self, soup: BeautifulSoup) -> str:
        """
        Извлечь статус книги
        """
        selectors = [
            '.book__status',
            '.book-status',
            '.status'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        
        return "Неизвестно"
    
    def _extract_genre(self, soup: BeautifulSoup) -> str:
        """
        Извлечь жанр книги
        """
        selectors = [
            '.book__genre',
            '.book-genre',
            '.genre',
            '.tag'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        
        return "Неизвестно"
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """
        Извлечь описание книги
        """
        selectors = [
            '.book__desc',
            '.book-description',
            '.description',
            '.book-intro'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        
        return "Нет описания"
    
    def _clean_chapter_content(self, content_elem) -> str:
        """
        Очистить содержимое главы от лишних элементов
        """
        # Удаляем ненужные элементы
        for unwanted in content_elem.select('script, style, .ad, .advertisement'):
            unwanted.decompose()
        
        # Получаем текст с сохранением абзацев
        paragraphs = []
        for p in content_elem.find_all(['p', 'div']):
            text = p.get_text(strip=True)
            if text and len(text) > 10:  # Игнорируем короткие строки
                paragraphs.append(text)
        
        return '\n\n'.join(paragraphs) if paragraphs else content_elem.get_text(strip=True)


def main():
    """
    Демонстрация работы парсера Qidian
    """
    print("📚 QIDIAN PARSER - Демонстрация")
    print("=" * 50)
    
    # Тестовая книга
    book_url = "https://www.qidian.com/book/1209977/"  # 斗破苍穹
    
    with QidianParser() as parser:
        try:
            # Получаем информацию о книге
            print("📖 Получение информации о книге...")
            book_info = parser.get_book_info(book_url)
            print(f"✅ Название: {book_info['title']}")
            print(f"✅ Автор: {book_info['author']}")
            print(f"✅ Жанр: {book_info['genre']}")
            print()
            
            # Скачиваем книгу (ограничиваем 3 главами для демо)
            print("📚 Скачивание книги...")
            results = parser.download_book(book_url, "./qidian_parsed", chapter_limit=3)
            
            # Показываем статистику
            stats = parser.get_stats()
            print(f"\n📊 СТАТИСТИКА:")
            print(f"   Всего запросов: {stats['total_requests']}")
            print(f"   Успешных: {stats['successful_requests']}")
            print(f"   Успешность: {stats['success_rate']:.1%}")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    main()