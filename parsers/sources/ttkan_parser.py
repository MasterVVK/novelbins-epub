#!/usr/bin/env python3
"""
Парсер TTKan (ttkan.co) на основе базового класса
Использует requests + BeautifulSoup (контент SSR, Selenium не нужен)
"""
import time
import random
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import re
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'base'))
from base_parser import BaseParser


class TtkanParser(BaseParser):
    """
    Парсер для ttkan.co (天天看小說)
    Китайская платформа веб-новелл с традиционными иероглифами
    """

    def __init__(self, auth_cookies: str = None, socks_proxy: str = None):
        super().__init__("ttkan")

        self.base_url = "https://ttkan.co"
        self.auth_cookies = auth_cookies
        self.socks_proxy = socks_proxy
        self.consecutive_errors = 0

        if socks_proxy:
            self._setup_proxy_session()

        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Referer': 'https://ttkan.co/',
        })

        if auth_cookies:
            for cookie in auth_cookies.split(';'):
                cookie = cookie.strip()
                if '=' in cookie:
                    name, value = cookie.split('=', 1)
                    self.session.cookies.set(name.strip(), value.strip())

    def _setup_proxy_session(self):
        """Настройка сессии с SOCKS прокси"""
        try:
            if ':' in self.socks_proxy:
                proxy_host, proxy_port = self.socks_proxy.split(':', 1)
                proxy_url = f'socks5://{proxy_host}:{proxy_port}'
                self.session.proxies = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                print(f"🌐 TTKan: Используем SOCKS прокси: {self.socks_proxy}")
        except Exception as e:
            print(f"⚠️ TTKan: Ошибка настройки прокси: {e}")

    def _extract_novel_id(self, url: str) -> str:
        """Извлекает slug новеллы из URL"""
        patterns = [
            r'/novel/chapters/([^/\?]+)',
            r'/novel/pagea/([^_]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return 'unknown'

    def _build_chapters_url(self, book_url: str) -> str:
        """Строит URL страницы списка глав"""
        novel_id = self._extract_novel_id(book_url)
        return f"{self.base_url}/novel/chapters/{novel_id}"

    def get_book_info(self, book_url: str) -> Dict:
        """Получить информацию о книге"""
        novel_id = self._extract_novel_id(book_url)
        chapters_url = self._build_chapters_url(book_url)

        html = self._get_page_content(chapters_url, timeout=15, description=f"Информация о книге {novel_id}")
        if not html:
            raise Exception(f"Не удалось получить страницу книги: {chapters_url}")

        soup = BeautifulSoup(html, 'html.parser')

        # Заголовок
        title_elem = soup.select_one('.novel_info h1')
        title = title_elem.get_text(strip=True) if title_elem else "Неизвестно"

        # Автор (ссылка формата /novel/search?q=@AuthorName)
        author_elem = soup.select_one('a[href*="search?q=@"]')
        author = author_elem.get_text(strip=True) if author_elem else "Неизвестно"

        # Описание
        desc_elem = soup.select_one('.description')
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        # Статус и жанр из .novel_info li
        status = "Неизвестно"
        genre = "Неизвестно"
        info_items = soup.select('.novel_info li')
        genre_keywords = ['仙俠', '玄幻', '都市', '武俠', '歷史', '軍事', '科幻', '言情', '奇幻', '輕小說', '懸疑', '遊戲', '體育', '同人']
        for item in info_items:
            text = item.get_text(strip=True)
            if '完結' in text:
                status = '完結'
            elif '連載' in text:
                status = '連載中'
            for kw in genre_keywords:
                if kw in text:
                    genre = kw

        # Считаем количество глав
        chapter_links = soup.select(f'a[href*="/novel/pagea/{novel_id}_"]')
        total_chapters = len(chapter_links)

        return {
            'book_id': novel_id,
            'title': title,
            'author': author,
            'description': description,
            'status': status,
            'genre': genre,
            'total_chapters': total_chapters
        }

    def get_chapter_list(self, book_url: str) -> List[Dict]:
        """Получить список глав книги"""
        novel_id = self._extract_novel_id(book_url)
        chapters_url = self._build_chapters_url(book_url)

        html = self._get_page_content(chapters_url, timeout=30, description=f"Список глав {novel_id}")
        if not html:
            raise Exception(f"Не удалось получить список глав: {chapters_url}")

        soup = BeautifulSoup(html, 'html.parser')

        # Ищем ссылки на главы по паттерну href
        chapter_links = soup.select(f'a[href*="/novel/pagea/{novel_id}_"]')

        if not chapter_links:
            # Fallback: ищем по более общему паттерну
            chapter_links = soup.select('a[href*="/novel/pagea/"]')
            chapter_links = [a for a in chapter_links if novel_id in a.get('href', '')]

        chapters = []
        for i, link in enumerate(chapter_links, 1):
            href = link.get('href', '')
            title = link.get_text(strip=True)

            if not href or not title:
                continue

            # Абсолютный URL
            if href.startswith('/'):
                full_url = f"{self.base_url}{href}"
            else:
                full_url = href

            # Извлекаем номер главы из URL
            chapter_match = re.search(r'_(\d+)\.html', href)
            chapter_number = int(chapter_match.group(1)) if chapter_match else i

            chapters.append({
                'number': i,
                'title': title,
                'url': full_url,
                'chapter_id': str(chapter_number),
            })

        print(f"📑 TTKan: найдено {len(chapters)} глав для {novel_id}")
        return chapters

    def get_chapter_content(self, chapter_url: str) -> Dict:
        """Получить содержимое главы"""
        html = self._get_page_content(chapter_url, timeout=15, description="Содержимое главы")
        if not html:
            self.consecutive_errors += 1
            raise Exception(f"Не удалось получить содержимое главы: {chapter_url}")

        self.consecutive_errors = 0
        soup = BeautifulSoup(html, 'html.parser')

        # Заголовок
        title_elem = soup.select_one('.title h1')
        title = title_elem.get_text(strip=True) if title_elem else "Неизвестная глава"

        # Контент — собираем все параграфы из .content
        content_elem = soup.select_one('.content')
        paragraphs = []
        if content_elem:
            for p in content_elem.find_all('p'):
                text = p.get_text(strip=True)
                if text:
                    paragraphs.append(text)

        content = '\n\n'.join(paragraphs) if paragraphs else ""

        if not content:
            raise Exception(f"Пустое содержимое главы: {chapter_url}")

        # chapter_id из URL
        chapter_match = re.search(r'_(\d+)\.html', chapter_url)
        chapter_id = chapter_match.group(1) if chapter_match else '0'

        return {
            'title': title,
            'content': content,
            'chapter_id': chapter_id,
            'word_count': len(content)
        }

    def _delay_between_requests(self):
        """Адаптивная пауза между запросами"""
        base_delay = 0.5
        if self.consecutive_errors > 0:
            base_delay *= (1 + self.consecutive_errors * 0.5)
            base_delay = min(base_delay, 30.0)
        delay = base_delay + random.uniform(0.2, 0.8)
        time.sleep(delay)
