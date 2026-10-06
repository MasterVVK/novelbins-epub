#!/usr/bin/env python3
"""
Парсер TTKan (ttkan.co) на основе базового класса
Использует requests + BeautifulSoup (контент SSR).
С 09.2026 сайт закрыт JS-проверкой браузера (gatekeeper, 403 challenge_required):
её проходит undetected-chromedriver, дальше requests работает с полученными
cookies и тем же User-Agent; при истечении clearance проверка проходится заново.
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

        self.base_url = "https://www.ttkan.co"
        self.auth_cookies = auth_cookies
        self.socks_proxy = socks_proxy
        self.consecutive_errors = 0
        # Gatekeeper clearance: cookies и UA браузера, прошедшего проверку
        self.gk_cookies = {}
        self.gk_user_agent = None
        self.chapter_request_count = 0
        self.batch_size = 50  # Сброс сессии каждые N глав

        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]

        if socks_proxy:
            self._setup_proxy_session()

        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
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
                proxy_url = f'socks5h://{proxy_host}:{proxy_port}'
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

    def get_book_info(self, book_url: str, max_retries: int = 3) -> Dict:
        """Получить информацию о книге"""
        novel_id = self._extract_novel_id(book_url)
        chapters_url = self._build_chapters_url(book_url)

        html = None
        for attempt in range(max_retries):
            html = self._get_page_content(chapters_url, timeout=300, description=f"Информация о книге {novel_id}")
            if html:
                break
            wait = 30 * (attempt + 1)
            print(f"⏳ TTKan: retry инфо книги {attempt + 1}/{max_retries}, ожидание {wait}с...")
            time.sleep(wait)
            self.reset_session()

        if not html:
            raise Exception(f"Не удалось получить страницу книги после {max_retries} попыток: {chapters_url}")

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

    def get_chapter_list(self, book_url: str, max_retries: int = 3) -> List[Dict]:
        """Получить список глав книги"""
        novel_id = self._extract_novel_id(book_url)
        chapters_url = self._build_chapters_url(book_url)

        html = None
        for attempt in range(max_retries):
            html = self._get_page_content(chapters_url, timeout=300, description=f"Список глав {novel_id}")
            if html:
                break
            wait = 30 * (attempt + 1)
            print(f"⏳ TTKan: retry список глав {attempt + 1}/{max_retries}, ожидание {wait}с...")
            time.sleep(wait)
            self.reset_session()

        if not html:
            raise Exception(f"Не удалось получить список глав после {max_retries} попыток: {chapters_url}")

        soup = BeautifulSoup(html, 'html.parser')

        # Ищем ссылки на главы по паттерну href
        chapter_links = soup.select(f'a[href*="/novel/pagea/{novel_id}_"]')

        if not chapter_links:
            # Fallback: ищем по более общему паттерну
            chapter_links = soup.select('a[href*="/novel/pagea/"]')
            chapter_links = [a for a in chapter_links if novel_id in a.get('href', '')]

        chapters = []
        seen_urls = set()
        for link in chapter_links:
            href = link.get('href', '')
            title = link.get_text(strip=True)

            # Нормализуем href для дедупликации (сайт дублирует список:
            # первый раз относительные /novel/pagea/..., второй — абсолютные https://www.ttkan.co/novel/pagea/...)
            normalized = re.sub(r'^https?://[^/]+', '', href)
            if not href or not title or normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            # Абсолютный URL
            if href.startswith('/'):
                full_url = f"{self.base_url}{href}"
            else:
                full_url = href

            # Извлекаем номер главы из URL
            chapter_match = re.search(r'_(\d+)\.html', href)
            chapter_number = int(chapter_match.group(1)) if chapter_match else len(chapters) + 1

            chapters.append({
                'number': len(chapters) + 1,
                'title': title,
                'url': full_url,
                'chapter_id': str(chapter_number),
            })

        print(f"📑 TTKan: найдено {len(chapters)} глав для {novel_id}")
        return chapters

    def reset_session(self):
        """Сброс HTTP сессии — новые TCP соединения, новый UA, чистые cookies"""
        self.session.close()

        import requests
        self.session = requests.Session()

        if self.socks_proxy:
            self._setup_proxy_session()

        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://ttkan.co/',
        })

        if self.auth_cookies:
            for cookie in self.auth_cookies.split(';'):
                cookie = cookie.strip()
                if '=' in cookie:
                    name, value = cookie.split('=', 1)
                    self.session.cookies.set(name.strip(), value.strip())

        self._apply_gatekeeper()

        self.consecutive_errors = 0
        print(f"🔄 TTKan: сессия сброшена (новый UA, новые соединения)")

    def _apply_gatekeeper(self):
        """Переносит clearance-cookies и UA браузера в requests-сессию"""
        if not self.gk_user_agent:
            return
        self.session.headers['User-Agent'] = self.gk_user_agent
        for name, value in self.gk_cookies.items():
            self.session.cookies.set(name, value, domain='www.ttkan.co')

    def _solve_gatekeeper(self, url: str, timeout: int = 120) -> bool:
        """Проходит JS-проверку браузера в undetected-chromedriver и забирает cookies"""
        import subprocess
        import undetected_chromedriver as uc

        print(f"🛡️ TTKan: проверка браузера (gatekeeper), открываем Chrome: {url}")
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1280,900')
        if self.socks_proxy:
            options.add_argument(f"--proxy-server=socks5://{self.socks_proxy.replace('socks5://', '')}")

        version_main = None
        try:
            result = subprocess.run([uc.find_chrome_executable(), '--version'],
                                    capture_output=True, text=True, timeout=5)
            version_match = re.search(r'(\d+)\.', result.stdout)
            if version_match:
                version_main = int(version_match.group(1))
        except Exception as e:
            print(f"   ⚠️ Не удалось определить версию Chrome: {e}")

        driver = None
        try:
            driver = uc.Chrome(options=options, version_main=version_main)
            driver.set_page_load_timeout(120)
            driver.get(url)
            start = time.time()
            while time.time() - start < timeout:
                html = driver.page_source
                if '__gatekeeper_challenge' not in driver.current_url and 'data-state="checking"' not in html \
                        and '/novel/' in html:
                    break
                time.sleep(2)
            else:
                print(f"❌ TTKan: проверка браузера не пройдена за {timeout}с")
                return False

            self.gk_user_agent = driver.execute_script("return navigator.userAgent")
            self.gk_cookies = {c['name']: c['value'] for c in driver.get_cookies()}
            print(f"✅ TTKan: проверка пройдена за {time.time() - start:.0f}с, cookies: {list(self.gk_cookies)}")
        except Exception as e:
            print(f"❌ TTKan: ошибка браузерной проверки: {e}")
            return False
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        self._apply_gatekeeper()
        return True

    def _get_page_content(self, url: str, timeout: int = 10, description: str = "") -> Optional[str]:
        """GET с обработкой gatekeeper: на 403 challenge_required проходит проверку и повторяет запрос"""
        for attempt in range(2):
            try:
                self.request_count += 1
                if description:
                    print(f"🌐 {description}: {url}")
                response = self.session.get(url, timeout=timeout)
                # Без Accept: text/html сайт отдаёт JSON challenge_required, с ним — HTML-страницу проверки
                if response.status_code == 403 and attempt == 0 and \
                        ('challenge_required' in response.text or '__gatekeeper_challenge' in response.text):
                    print(f"🛡️ TTKan: 403 challenge_required — нужна проверка браузера")
                    if self._solve_gatekeeper(url):
                        continue
                response.raise_for_status()
                self.success_count += 1
                return response.text
            except Exception as e:
                print(f"❌ Ошибка запроса к {url}: {e}")
                return None
        return None

    def get_chapter_content(self, chapter_url: str, max_retries: int = 3) -> Dict:
        """Получить содержимое главы"""
        self.chapter_request_count += 1

        # Сброс сессии каждые batch_size глав
        if self.chapter_request_count > 1 and self.chapter_request_count % self.batch_size == 1:
            batch_pause = random.uniform(180, 360)  # 3-6 минут
            print(f"⏸️ TTKan: батч-пауза {batch_pause:.0f}с после {self.chapter_request_count - 1} глав...")
            time.sleep(batch_pause)
            self.reset_session()

        # Ротация User-Agent при каждом запросе (clearance привязан к UA браузера — тогда не ротируем)
        if not self.gk_user_agent:
            self.session.headers['User-Agent'] = random.choice(self.user_agents)
        # Referer как при чтении — предыдущая глава или список
        self.session.headers['Referer'] = chapter_url.rsplit('_', 1)[0] + '_' + str(max(1, int(re.search(r'_(\d+)\.html', chapter_url).group(1)) - 1)) + '.html' if re.search(r'_(\d+)\.html', chapter_url) else 'https://ttkan.co/'

        html = None
        for attempt in range(max_retries):
            html = self._get_page_content(chapter_url, timeout=20, description="Содержимое главы")
            if html:
                break
            self.consecutive_errors += 1
            # Экспоненциальный backoff: 30с, 120с, 300с
            wait = min(30 * (2 ** attempt), 300)
            print(f"⏳ TTKan: retry {attempt + 1}/{max_retries}, ожидание {wait}с + сброс сессии...")
            time.sleep(wait)
            self.reset_session()

        if not html:
            raise Exception(f"Не удалось получить содержимое главы после {max_retries} попыток: {chapter_url}")

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
