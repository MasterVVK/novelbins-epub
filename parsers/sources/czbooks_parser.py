#!/usr/bin/env python3
"""
Парсер для czbooks.net - платформа китайских веб-новелл
Поддержка:
- Selenium для обхода Cloudflare
- SOCKS прокси
- Авторизация через cookies
- VIP главы
"""
import time
import random
import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import sys
import os

# Selenium для обхода Cloudflare
# Приоритет: undetected-chromedriver > selenium
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    selenium_available = True
    use_undetected = True
    print("✅ Используется undetected-chromedriver для обхода Cloudflare")
except ImportError:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        selenium_available = True
        use_undetected = False
        print("⚠️ Используется обычный Selenium (рекомендуется undetected-chromedriver)")
    except ImportError:
        selenium_available = False
        use_undetected = False
        print("⚠️ Selenium не установлен. Установите: pip install selenium")

# Добавляем путь к базовому классу
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'base'))
from base_parser import BaseParser


class CZBooksParser(BaseParser):
    """
    Парсер для czbooks.net

    Особенности:
    - Обход Cloudflare через Selenium
    - Поддержка SOCKS прокси
    - Авторизация через cookies
    - Обработка VIP глав
    - Антидетект для webdriver
    """

    def __init__(self, auth_cookies: str = None, socks_proxy: str = None, headless: bool = True, cloudflare_max_attempts: int = 5):
        """
        Инициализация парсера

        Args:
            auth_cookies: Cookie строка для авторизации
            socks_proxy: SOCKS прокси в формате host:port
            headless: Использовать headless режим (True) или нет (False)
                     ВАЖНО: Cloudflare лучше обходится в non-headless режиме,
                     но требуется дисплей (Xvfb на сервере)
            cloudflare_max_attempts: Количество попыток прохождения Cloudflare (по умолчанию 5)
        """
        super().__init__("czbooks")

        if not selenium_available:
            raise ImportError("Selenium требуется для парсинга czbooks.net. Установите: pip install selenium")

        self.base_url = "https://czbooks.net"
        self.auth_cookies = auth_cookies
        self.socks_proxy = socks_proxy
        self.headless = headless
        self.driver = None

        # Счетчик ошибок для адаптивных пауз
        self.consecutive_errors = 0

        # Счетчик запросов для перезапуска браузера
        self.request_count = 0
        self.max_requests_before_restart = 100  # Перезапускаем браузер каждые 100 запросов

        # Настройка Cloudflare challenge
        self.cloudflare_max_attempts = cloudflare_max_attempts

        print(f"📚 CZBooks Parser инициализирован")
        if auth_cookies:
            print(f"   🔐 Авторизация: включена ({len(auth_cookies)} символов)")
        if socks_proxy:
            print(f"   🌐 Прокси: {socks_proxy}")

    def restart_driver(self):
        """Перезапустить браузер для освобождения памяти"""
        print("🔄 Перезапуск браузера для освобождения памяти...")
        if self.driver:
            try:
                self.driver.quit()
                print("   ✅ Старый браузер закрыт")
            except Exception as e:
                print(f"   ⚠️ Ошибка закрытия браузера: {e}")
            finally:
                self.driver = None

        # Небольшая пауза перед новым запуском
        time.sleep(2)

        # Сбрасываем счетчик запросов
        self.request_count = 0

        # Инициализируем новый браузер
        self._init_selenium()
        print("   ✅ Новый браузер запущен")

    def _init_selenium(self):
        """Инициализация Selenium с обходом Cloudflare и антидетектом"""
        if self.driver:
            return

        print("🚀 Инициализация Selenium драйвера...")

        if use_undetected:
            # Используем undetected-chromedriver для автоматического обхода
            print("   🔧 Режим: undetected-chromedriver")

            options = uc.ChromeOptions()

            # Основные опции
            if self.headless:
                # Headless режим (для серверов без дисплея)
                # ВНИМАНИЕ: Cloudflare может блокировать headless режим!
                options.add_argument('--headless=new')
                print("   ⚠️ Используется headless режим (может блокироваться Cloudflare)")
            else:
                # Non-headless режим (лучше обход, но требует дисплей)
                print("   ✅ Используется non-headless режим (лучший обход Cloudflare)")

            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')

            # Дополнительные опции для снижения детекции
            options.add_argument('--disable-blink-features=AutomationControlled')
            if not self.headless:
                options.add_argument('--start-maximized')

            # SOCKS прокси если настроен
            if self.socks_proxy:
                # Убираем socks5:// если уже есть
                proxy_url = self.socks_proxy.replace('socks5://', '')
                options.add_argument(f'--proxy-server=socks5://{proxy_url}')
                print(f"   🌐 Прокси настроен: socks5://{proxy_url}")

            # Создаем драйвер с undetected-chromedriver
            # НЕ указываем явные пути - пусть uc управляет своей копией драйвера
            # Это решает проблему Permission denied на /usr/bin/chromedriver
            try:
                self.driver = uc.Chrome(
                    options=options,
                    version_main=141  # Указываем версию Chrome явно
                )
                print("   ✅ undetected-chromedriver инициализирован")
            except Exception as e:
                print(f"   ⚠️ Ошибка инициализации с версией 141, пробуем автоопределение: {e}")
                try:
                    self.driver = uc.Chrome(options=options)
                    print("   ✅ undetected-chromedriver инициализирован (автоопределение)")
                except Exception as e2:
                    print(f"   ❌ Не удалось инициализировать undetected-chromedriver: {e2}")
                    raise

            # Увеличиваем таймауты для Cloudflare challenge
            self.driver.set_page_load_timeout(300)  # 5 минут на загрузку страницы
            self.driver.set_script_timeout(60)  # 1 минута на выполнение скриптов

            # ВАЖНО: Увеличиваем таймаут HTTP-соединения между Selenium и Chrome
            # Это критично для прохождения долгих Cloudflare challenge
            try:
                from selenium.webdriver.remote.remote_connection import RemoteConnection
                RemoteConnection.set_timeout(300)  # 5 минут
                print("   ⏱️ Таймауты установлены: 300s загрузка, 300s HTTP соединение")
            except Exception as e:
                print(f"   ⚠️ Не удалось установить HTTP таймаут: {e}")
                print("   ⏱️ Таймауты установлены: 300s загрузка, 60s скрипты")

            # Автозапуск VNC для веб-трансляции браузера
            self._start_vnc_if_needed()

        else:
            # Fallback на обычный Selenium
            print("   🔧 Режим: обычный Selenium")

            chrome_options = Options()

            # Основные опции
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')

            # User-Agent (реалистичный браузер)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            # Обход webdriver detection
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # Дополнительные опции для обхода детекции
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-renderer-backgrounding')

            # SOCKS прокси если настроен
            if self.socks_proxy:
                # Убираем socks5:// если уже есть
                proxy_url = self.socks_proxy.replace('socks5://', '')
                chrome_options.add_argument(f'--proxy-server=socks5://{proxy_url}')
                print(f"   🌐 Прокси настроен: socks5://{proxy_url}")

            # Путь к Chromium
            chrome_options.binary_location = '/usr/bin/chromium-browser'

            # Создаем драйвер
            try:
                service = Service('/usr/bin/chromedriver')
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e:
                print(f"⚠️ Ошибка создания драйвера с Service, пробуем без него: {e}")
                self.driver = webdriver.Chrome(options=chrome_options)

            # Убираем webdriver флаг через JavaScript
            try:
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': '''
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });

                        // Дополнительные маскировки
                        window.navigator.chrome = {
                            runtime: {}
                        };

                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });

                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['en-US', 'en', 'zh-CN', 'zh']
                        });
                    '''
                })
            except:
                pass  # Не критично если не удалось

            # Увеличиваем таймауты для Cloudflare challenge
            self.driver.set_page_load_timeout(300)  # 5 минут на загрузку страницы
            self.driver.set_script_timeout(60)  # 1 минута на выполнение скриптов
            print("   ⏱️ Таймауты установлены: 300s загрузка, 60s скрипты")

        # Устанавливаем cookies если есть
        if self.auth_cookies:
            print("   🍪 Установка cookies...")
            # Используем JavaScript для контроля загрузки
            try:
                # Запускаем загрузку страницы
                self.driver.set_page_load_timeout(30)  # Короткий таймаут для начальной загрузки
                self.driver.get(self.base_url)
            except Exception as e:
                # Таймаут - это нормально, страница может грузиться долго
                print(f"   ⏳ Начальная загрузка прервана (ожидаемо): {type(e).__name__}")
                # Принудительно останавливаем загрузку
                try:
                    self.driver.execute_script("window.stop();")
                except:
                    pass

            # Восстанавливаем нормальный таймаут
            self.driver.set_page_load_timeout(300)

            # Ждем прохождения Cloudflare challenge
            initial_wait = 20 + random.uniform(2, 5)
            print(f"   ⏳ Ожидание прохождения Cloudflare ({initial_wait:.1f}s)...")
            time.sleep(initial_wait)

            # Проверяем состояние страницы
            try:
                page_source = self.driver.page_source

                # Дополнительное ожидание если Cloudflare активен
                max_cf_attempts = 2
                for attempt in range(max_cf_attempts):
                    if 'Cloudflare' in page_source and 'Just a moment' in page_source:
                        wait_time = 15
                        print(f"   ⚠️ Cloudflare challenge активен, попытка {attempt+1}/{max_cf_attempts}, ждем {wait_time}s...")
                        time.sleep(wait_time)
                        page_source = self.driver.page_source
                    else:
                        break

                if len(page_source) > 5000:
                    print(f"   ✅ Cloudflare пройден ({len(page_source)} символов)")
                else:
                    print(f"   ⚠️ Возможно Cloudflare не пройден ({len(page_source)} символов)")
                    print(f"   📄 Превью страницы: {page_source[:500]}")
            except Exception as e:
                print(f"   ⚠️ Ошибка проверки страницы: {e}")

            cookies_set = 0
            for cookie_pair in self.auth_cookies.split(';'):
                if '=' in cookie_pair:
                    name, value = cookie_pair.strip().split('=', 1)
                    try:
                        self.driver.add_cookie({
                            'name': name.strip(),
                            'value': value.strip(),
                            'domain': '.czbooks.net'
                        })
                        cookies_set += 1
                    except Exception as e:
                        print(f"   ⚠️ Ошибка установки cookie {name}: {e}")
                        continue

            print(f"   ✅ Установлено cookies: {cookies_set}")

        print("   ✅ Selenium драйвер готов")

    def _start_vnc_if_needed(self):
        """Запустить VNC сервер для веб-трансляции, если еще не запущен"""
        import subprocess
        import os

        try:
            # Получаем текущий DISPLAY
            display = os.environ.get('DISPLAY', ':99')

            # Проверяем, запущен ли x11vnc на порту 5900
            result = subprocess.run(
                ['pgrep', '-f', f'x11vnc.*rfbport 5900'],
                capture_output=True
            )

            if result.returncode != 0:
                # x11vnc не запущен, запускаем
                print(f"   🖥️ Запуск VNC сервера для дисплея {display}...")

                # Находим Xauthority файл для текущего дисплея
                xauth = None
                try:
                    # Ищем процесс Xvfb для текущего дисплея
                    xvfb_result = subprocess.run(
                        ['ps', 'aux'],
                        capture_output=True,
                        text=True
                    )
                    for line in xvfb_result.stdout.split('\n'):
                        if f'Xvfb {display}' in line and '-auth' in line:
                            parts = line.split()
                            for i, part in enumerate(parts):
                                if part == '-auth' and i + 1 < len(parts):
                                    xauth = parts[i + 1]
                                    break
                            if xauth:
                                break
                except:
                    pass

                # Запускаем x11vnc
                cmd = [
                    'x11vnc',
                    '-display', display,
                    '-rfbport', '5900',
                    '-shared',
                    '-forever',
                    '-nopw',
                    '-bg',
                    '-o', '/tmp/x11vnc.log'
                ]

                if xauth:
                    cmd.extend(['-auth', xauth])

                subprocess.run(cmd, capture_output=True)
                print(f"   ✅ VNC сервер запущен на порту 5900")
                print(f"   🌐 Веб-доступ: http://localhost:6080/vnc.html")
            else:
                print(f"   ✅ VNC сервер уже запущен")

        except Exception as e:
            print(f"   ⚠️ Не удалось запустить VNC: {e}")
            # Продолжаем работу даже если VNC не запустился

    def _get_page_with_selenium(self, url: str, wait_selector: str = None, wait_time: int = 15) -> str:
        """
        Загрузка страницы через Selenium с обходом Cloudflare

        Args:
            url: URL страницы
            wait_selector: CSS селектор для ожидания (опционально)
            wait_time: Максимальное время ожидания в секундах

        Returns:
            HTML содержимое страницы
        """
        # Проверяем, нужен ли перезапуск браузера
        self.request_count += 1
        if self.request_count >= self.max_requests_before_restart:
            print(f"   📊 Достигнут лимит запросов ({self.request_count}), перезапускаем браузер...")
            self.restart_driver()

        self._init_selenium()

        print(f"🌐 Загрузка страницы: {url}")

        try:
            self.driver.get(url)

            # Базовая задержка для прохождения Cloudflare challenge
            initial_wait = 15 + random.uniform(2, 5)
            print(f"   ⏳ Ожидание прохождения Cloudflare ({initial_wait:.1f}s)...")
            time.sleep(initial_wait)

            # Если указан селектор, ждем его появления
            if wait_selector:
                try:
                    print(f"   ⏳ Ожидание элемента: {wait_selector}")
                    WebDriverWait(self.driver, wait_time).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                    )
                    print(f"   ✅ Элемент найден")
                except Exception as e:
                    print(f"   ⚠️ Таймаут ожидания селектора: {e}")
                    # Продолжаем даже если селектор не найден

            # Дополнительная проверка на Cloudflare challenge
            page_source = self.driver.page_source

            # Проверяем, прошли ли мы Cloudflare (несколько попыток)
            max_attempts = self.cloudflare_max_attempts
            for attempt in range(max_attempts):
                # Проверяем различные варианты Cloudflare challenge
                cf_indicators = [
                    ('Cloudflare' in page_source and 'Just a moment' in page_source),
                    ('Verify you are human' in page_source),  # Turnstile
                    ('turnstile' in page_source.lower() and 'challenge' in page_source.lower()),
                    ('cf-chl' in page_source),  # Cloudflare challenge ID
                ]

                if any(cf_indicators):
                    wait_time = 20 + (attempt * 10)  # Увеличено время ожидания
                    print(f"   ⚠️ Cloudflare challenge активен, попытка {attempt + 1}/{max_attempts}, ждем {wait_time}s...")
                    time.sleep(wait_time)
                    page_source = self.driver.page_source
                else:
                    break

            # Проверка успешности - проверяем, что это не Cloudflare
            cf_still_active = any([
                ('Verify you are human' in page_source),
                ('cf-chl' in page_source and 'challenge' in page_source.lower()),
            ])

            if cf_still_active:
                print(f"   ❌ Cloudflare challenge не пройден после {max_attempts} попыток")
                print(f"   💡 Рекомендация: добавьте auth_cookies в настройки новеллы")
                self.consecutive_errors += 1
                raise Exception("Не удалось пройти Cloudflare Turnstile challenge. Требуются действительные cookies.")

            if len(page_source) > 5000:
                print(f"   ✅ Страница загружена ({len(page_source)} символов)")
                self.consecutive_errors = 0
                return page_source
            else:
                print(f"   ⚠️ Подозрительно малый размер страницы: {len(page_source)}")
                self.consecutive_errors += 1
                return page_source

        except Exception as e:
            print(f"   ❌ Ошибка загрузки страницы: {e}")
            self.consecutive_errors += 1
            raise

    def get_book_info(self, book_url: str) -> Dict:
        """
        Получить информацию о книге

        Args:
            book_url: URL книги на czbooks.net

        Returns:
            Dict с информацией о книге
        """
        print(f"\n📖 Получение информации о книге...")

        html = self._get_page_with_selenium(
            book_url,
            wait_selector='h1, .book-title, [class*="title"]',
            wait_time=20
        )

        soup = BeautifulSoup(html, 'html.parser')

        # Извлекаем book_id из URL
        book_id = self._extract_book_id(book_url)

        # Парсим информацию
        title = self._extract_title(soup)
        author = self._extract_author(soup)
        description = self._extract_description(soup)
        genre = self._extract_genre(soup)
        status = self._extract_status(soup)

        book_info = {
            'book_id': book_id,
            'title': title,
            'author': author,
            'description': description,
            'status': status,
            'genre': genre,
            'total_chapters': 0  # Будет обновлено в get_chapter_list
        }

        print(f"   ✅ Название: {title}")
        print(f"   ✅ Автор: {author}")
        print(f"   ✅ Жанр: {genre}")

        return book_info

    def get_chapter_list(self, book_url: str) -> List[Dict]:
        """
        Получить список глав книги

        Args:
            book_url: URL книги

        Returns:
            List[Dict] со списком глав
        """
        print(f"\n📚 Получение списка глав...")

        html = self._get_page_with_selenium(
            book_url,
            wait_selector='a[href*="/"], .chapter-list, #chapters',
            wait_time=20
        )

        soup = BeautifulSoup(html, 'html.parser')

        # Ищем ссылки на главы
        chapter_links = self._find_chapter_links(soup, book_url)

        if not chapter_links:
            print("   ⚠️ Главы не найдены, попытка прокрутки страницы...")
            # Пробуем прокрутить страницу для загрузки динамического контента
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            chapter_links = self._find_chapter_links(soup, book_url)

        chapters = []
        for i, link in enumerate(chapter_links, 1):
            href = link.get('href', '')
            title = link.get_text(strip=True)

            if not href or not title:
                continue

            # Преобразуем относительные URL в абсолютные
            if href.startswith('http://') or href.startswith('https://'):
                # Уже абсолютный URL
                full_url = href
            elif href.startswith('//'):
                # Protocol-relative URL
                full_url = f"https:{href}"
            elif href.startswith('/'):
                # Абсолютный путь от корня домена
                full_url = f"{self.base_url}{href}"
            else:
                # Относительный путь от текущей страницы
                full_url = f"{book_url.rstrip('/')}/{href}"

            # Извлекаем chapter_id
            chapter_id = self._extract_chapter_id(full_url)

            chapters.append({
                'number': i,
                'title': title,
                'url': full_url,
                'chapter_id': chapter_id,
                'word_count': 0
            })

        print(f"   ✅ Найдено глав: {len(chapters)}")

        if chapters:
            print(f"\n   Первые 5 глав:")
            for ch in chapters[:5]:
                print(f"      {ch['number']}. {ch['title'][:50]}")

        return chapters

    def get_chapter_content(self, chapter_url: str) -> Dict:
        """
        Получить содержимое главы

        Args:
            chapter_url: URL главы

        Returns:
            Dict с содержимым главы
        """
        print(f"\n📄 Загрузка главы: {chapter_url}")

        html = self._get_page_with_selenium(
            chapter_url,
            wait_selector='.chapter-content, #content, article, main',
            wait_time=20
        )

        soup = BeautifulSoup(html, 'html.parser')

        # Извлекаем заголовок
        title = self._extract_chapter_title(soup)

        # Извлекаем контент
        content = self._extract_chapter_content(soup)

        # Проверяем блокировку
        is_locked = self._check_locked(soup, content)

        result = {
            'title': title,
            'content': content,
            'chapter_id': self._extract_chapter_id(chapter_url),
            'word_count': len(content),
            'is_locked': is_locked
        }

        if is_locked:
            print(f"   🔒 Глава заблокирована (превью: {len(content)} символов)")
        else:
            print(f"   ✅ Глава загружена: {len(content)} символов")

        return result

    def _extract_book_id(self, url: str) -> str:
        """Извлечь ID книги из URL"""
        # Паттерны для czbooks.net
        patterns = [
            r'/n/([^/\?]+)',  # /n/ul6pe
            r'/novel/([^/\?]+)',  # /novel/123
            r'/book/([^/\?]+)',  # /book/123
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return 'unknown'

    def _extract_chapter_id(self, url: str) -> str:
        """Извлечь ID главы из URL"""
        # Паттерны для ID главы
        patterns = [
            r'/n/[^/]+/([^/\?]+)',  # /n/ul6pe/chapter-1
            r'/chapter/([^/\?]+)',  # /chapter/123
            r'/c/([^/\?]+)',  # /c/123
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return 'unknown'

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлечь название книги"""
        selectors = [
            'h1.book-title',
            'h1.novel-title',
            'h1.title',
            '.book-info h1',
            'h1',
            '[class*="title"]'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # Исключаем служебные заголовки
                if text and len(text) > 2 and text.lower() not in ['czbooks.net', 'just a moment']:
                    return text

        return "Unknown Title"

    def _extract_author(self, soup: BeautifulSoup) -> str:
        """Извлечь автора книги"""
        selectors = [
            '.author',
            '.book-author',
            '[class*="author"]',
            '.writer',
            '[rel="author"]',
            '.book-info .author'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # Удаляем префиксы
                text = text.replace('作者：', '').replace('Author:', '').replace('作者', '').strip()
                if text and len(text) > 1 and len(text) < 100:
                    return text

        return "Unknown Author"

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Извлечь описание книги"""
        selectors = [
            '.description',
            '.synopsis',
            '.book-desc',
            '[class*="desc"]',
            '.intro',
            '.summary',
            '.book-info .description'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text and len(text) > 20:
                    return text

        return ""

    def _extract_genre(self, soup: BeautifulSoup) -> str:
        """Извлечь жанр книги"""
        selectors = [
            '.genre',
            '.category',
            '[class*="genre"]',
            '.tag',
            '.book-genre'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)

        return "Unknown"

    def _extract_status(self, soup: BeautifulSoup) -> str:
        """Извлечь статус книги"""
        selectors = [
            '.status',
            '.book-status',
            '[class*="status"]'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)

        return "Unknown"

    def _find_chapter_links(self, soup: BeautifulSoup, book_url: str) -> List:
        """Найти ссылки на главы"""
        # Извлекаем book_id для фильтрации ссылок
        book_id = self._extract_book_id(book_url)

        # Пробуем различные селекторы
        selectors = [
            f'a[href*="/n/{book_id}/"]',  # Прямые ссылки на главы этой книги
            '.chapter-list a',
            '#chapters a',
            '.chapters a',
            '.toc a',
            'a[href*="/chapter/"]',
            'a[href*="/c/"]'
        ]

        all_links = []
        for selector in selectors:
            links = soup.select(selector)
            if links:
                print(f"   🔍 Селектор '{selector}': найдено {len(links)} ссылок")
                all_links.extend(links)

        # Удаляем дубликаты по href
        seen_hrefs = set()
        unique_links = []

        for link in all_links:
            href = link.get('href', '')
            if href and href not in seen_hrefs:
                # Проверяем что это действительно ссылка на главу
                if any(pattern in href for pattern in ['/chapter', '/c/', f'/n/{book_id}/']):
                    seen_hrefs.add(href)
                    unique_links.append(link)

        print(f"   ✅ Уникальных ссылок на главы: {len(unique_links)}")
        return unique_links

    def _extract_chapter_title(self, soup: BeautifulSoup) -> str:
        """Извлечь заголовок главы"""
        selectors = [
            '.chapter-title',
            'h1.title',
            'h1',
            'h2',
            '[class*="chapter"][class*="title"]'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text and len(text) > 2:
                    return text

        return "Unknown Chapter"

    def _extract_chapter_content(self, soup: BeautifulSoup) -> str:
        """Извлечь содержимое главы"""
        selectors = [
            '.chapter-content',
            '#content',
            '.content',
            'article.chapter',
            'article',
            'main',
            '[class*="chapter"][class*="content"]'
        ]

        for selector in selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Удаляем лишние элементы
                for unwanted in content_elem.select('script, style, .ad, .advertisement, nav, .navigation, .share, .comment'):
                    unwanted.decompose()

                # Сначала пробуем извлечь параграфы <p>
                paragraphs = []
                for p in content_elem.find_all('p'):
                    text = p.get_text(strip=True)
                    if text and len(text) > 10:
                        # Убираем лишние пробелы
                        text = re.sub(r'\s+', ' ', text)
                        paragraphs.append(text)

                if paragraphs and len(paragraphs) > 2:
                    content = '\n\n'.join(paragraphs)
                    print(f"      📝 Извлечено параграфов <p>: {len(paragraphs)}")
                    return content

                # Если параграфов мало, работаем с <br> тегами
                # czbooks.net использует <br> вместо <p>
                # Используем get_text(separator='\n') чтобы сохранить переносы строк
                full_text = content_elem.get_text(separator='\n', strip=True)

                # Разбиваем по переносам и фильтруем пустые строки
                lines = [line.strip() for line in full_text.split('\n') if line.strip()]

                # Объединяем строки обратно с двойными переносами между параграфами
                content = '\n\n'.join(lines)

                if len(content) > 100:
                    print(f"      📝 Извлечено строк с <br>: {len(lines)}")
                    return content

        return "Content not found"

    def _check_locked(self, soup: BeautifulSoup, content: str) -> bool:
        """Проверить блокировку главы"""
        # Проверяем только длину контента
        # Маркеры "vip", "lock" могут быть в рекламе/навигации
        # Поэтому полагаемся только на длину текста

        # Если контент слишком короткий - вероятно превью
        if len(content) < 500:
            return True

        # Проверяем на явные маркеры блокировки в САМОМ КОНТЕНТЕ
        content_lower = content.lower()
        lock_phrases = [
            'this chapter is locked',
            'unlock this chapter',
            'subscribe to read',
            'premium content',
            'vip章节',
            '本章需要订阅',
            '订阅后可阅读'
        ]

        for phrase in lock_phrases:
            if phrase in content_lower:
                return True

        return False

    def _delay_between_requests(self):
        """Адаптивная пауза между запросами"""
        base_delay = 3.0

        # Увеличиваем паузу при ошибках
        if self.consecutive_errors > 0:
            base_delay *= (1 + self.consecutive_errors * 0.5)

        # Максимум 30 секунд
        base_delay = min(base_delay, 30.0)

        # Случайная составляющая
        random_factor = random.uniform(0.5, 1.5)
        delay = base_delay + random_factor

        print(f"⏳ Пауза {delay:.1f}s (ошибок: {self.consecutive_errors})...")
        time.sleep(delay)

    def get_cookies(self):
        """
        Извлечь cookies из браузера Selenium

        Returns:
            str: Cookies в формате JSON или None если драйвер не доступен
        """
        if not self.driver:
            return None

        try:
            import json
            cookies = self.driver.get_cookies()

            # Преобразуем в формат, который ожидает Novel model
            cookies_dict = {}
            for cookie in cookies:
                cookies_dict[cookie['name']] = cookie['value']

            cookies_json = json.dumps(cookies_dict, ensure_ascii=False)
            print(f"   🍪 Извлечено {len(cookies_dict)} cookies из браузера")
            return cookies_json

        except Exception as e:
            print(f"   ⚠️ Ошибка извлечения cookies: {e}")
            return None

    def close(self):
        """Закрыть Selenium драйвер и сессию"""
        if self.driver:
            try:
                self.driver.quit()
                print("   ✅ Selenium драйвер закрыт")
            except Exception as e:
                print(f"   ⚠️ Ошибка закрытия драйвера: {e}")
            finally:
                self.driver = None

        super().close()


def main():
    """
    Демонстрация работы парсера czbooks.net
    """
    print("=" * 60)
    print("📚 CZBOOKS PARSER - Демонстрация")
    print("=" * 60)

    # Тестовая книга
    test_url = "https://czbooks.net/n/ul6pe"

    parser = CZBooksParser()

    try:
        # Получаем информацию о книге
        print("\n1️⃣ Получение информации о книге...")
        book_info = parser.get_book_info(test_url)
        print(f"\n📖 Результат:")
        print(f"   Название: {book_info['title']}")
        print(f"   Автор: {book_info['author']}")
        print(f"   ID: {book_info['book_id']}")

        # Получаем список глав (первые 3)
        print("\n2️⃣ Получение списка глав...")
        chapters = parser.get_chapter_list(test_url)

        if chapters:
            print(f"\n📚 Найдено глав: {len(chapters)}")

            # Загружаем первую главу
            print("\n3️⃣ Загрузка первой главы...")
            first_chapter = chapters[0]
            content = parser.get_chapter_content(first_chapter['url'])

            print(f"\n📄 Результат:")
            print(f"   Заголовок: {content['title']}")
            print(f"   Размер: {content['word_count']} символов")
            print(f"   Заблокирована: {content['is_locked']}")
            print(f"\n   Превью контента:")
            print(f"   {content['content'][:300]}...")

        print("\n" + "=" * 60)
        print("✅ Демонстрация завершена")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    finally:
        parser.close()


if __name__ == "__main__":
    main()
