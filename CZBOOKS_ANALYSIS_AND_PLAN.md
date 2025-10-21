# Детальный анализ web_app и план добавления источника czbooks.net

## 📊 Общая информация о проекте

Дата анализа: 2025-10-13
Цель: Добавить поддержку czbooks.net как нового источника для парсинга новелл

---

## 1. 🏗️ Архитектура web_app

### 1.1 Структура приложения

```
web_app/
├── app/
│   ├── __init__.py              # Фабрика Flask приложения, настройка расширений
│   ├── models/                  # SQLAlchemy модели
│   │   ├── novel.py            # Модель новеллы (главная)
│   │   ├── chapter.py          # Модель главы
│   │   ├── translation.py      # Переводы
│   │   ├── glossary.py         # Глоссарий терминов
│   │   ├── task.py             # Задачи (Celery)
│   │   └── ...
│   ├── services/                # Бизнес-логика
│   │   ├── parser_service.py   # ⭐ Основной сервис парсинга
│   │   ├── translator_service.py
│   │   ├── editor_service.py
│   │   └── ...
│   ├── api/                     # REST API endpoints
│   │   ├── novels.py           # CRUD операции новелл
│   │   ├── tasks.py            # Управление задачами
│   │   └── ...
│   ├── templates/               # Jinja2 шаблоны
│   ├── static/                  # CSS, JS, изображения
│   └── views.py                 # Web UI views
├── config/                      # Конфигурация приложения
├── migrations/                  # Alembic миграции БД
├── instance/                    # Runtime файлы (EPUB, uploads)
└── run.py                       # Точка входа

parsers/                         # 🔥 Система парсеров (корень проекта)
├── __init__.py
├── base/
│   └── base_parser.py          # Абстрактный базовый класс
├── sources/
│   ├── qidian_parser.py        # Парсер Qidian
│   └── epub_parser.py          # Парсер EPUB файлов
└── parser_factory.py           # ⭐ Фабрика парсеров
```

### 1.2 Ключевые компоненты

#### **1.2.1 Модель Novel (web_app/app/models/novel.py)**

Основные поля:
- `source_type`: Тип источника ('novelbins', 'qidian', 'epub', etc.)
- `source_url`: URL источника
- `auth_cookies`: Cookies для авторизации
- `vip_cookies`: VIP cookies для премиум контента
- `socks_proxy`: SOCKS прокси для обхода блокировок
- `config`: JSON конфигурация (max_chapters, filter_text, etc.)

#### **1.2.2 WebParserService (web_app/app/services/parser_service.py)**

Основной сервис для парсинга в web-приложении. Ключевые методы:

```python
class WebParserService:
    def parse_novel_chapters(self, novel: Novel) -> List[dict]
        # Парсинг списка глав с использованием новой системы парсеров
        # Возвращает: [{'url': str, 'title': str, 'number': int}, ...]

    def parse_chapter_content(self, chapter_url: str, chapter_number: int, novel: Novel) -> str
        # Парсинг содержимого главы
        # Возвращает: текст главы

    def _parse_with_new_system(self, novel: Novel, novel_url: str) -> List[dict]
        # Использует систему parsers/ через create_parser_from_url()

    def _parse_with_legacy_system(self, novel: Novel, novel_url: str) -> List[dict]
        # Fallback на requests + BeautifulSoup
```

**Важно:** Сервис автоматически определяет источник и создает подходящий парсер через `create_parser_from_url()`

#### **1.2.3 ParserFactory (parsers/parser_factory.py)**

Центральный механизм для создания парсеров:

```python
class ParserFactory:
    _parsers = {
        'qidian': QidianParser,
        'epub': EPUBParser,
        # Здесь будет 'czbooks': CZBooksParser
    }

    _url_patterns = {
        r'qidian\.com': 'qidian',
        r'\.epub$': 'epub',
        # Здесь будет r'czbooks\.net': 'czbooks'
    }

    @classmethod
    def create_parser_from_url(url, auth_cookies, socks_proxy) -> BaseParser
        # Автоматически определяет парсер по URL
```

**Ключевая особенность:** Фабрика поддерживает регистрацию новых парсеров через `register_parser()`

#### **1.2.4 BaseParser (parsers/base/base_parser.py)**

Абстрактный базовый класс для всех парсеров:

```python
class BaseParser(ABC):
    @abstractmethod
    def get_book_info(self, book_url: str) -> Dict
        # Информация о книге: title, author, description, genre

    @abstractmethod
    def get_chapter_list(self, book_url: str) -> List[Dict]
        # Список глав: [{'number': int, 'title': str, 'url': str, 'chapter_id': str}]

    @abstractmethod
    def get_chapter_content(self, chapter_url: str) -> Dict
        # Содержимое главы: {'title': str, 'content': str, 'is_locked': bool}

    def close(self)
        # Закрытие сессии
```

---

## 2. 🔍 Анализ существующих парсеров

### 2.1 QidianParser - Эталонная реализация

**Особенности:**
1. **Selenium для обхода защиты**: Использует headless Chrome для JS-страниц
2. **SOCKS прокси**: Поддержка `socks_proxy` параметра
3. **Авторизация**: Поддержка обычных и VIP cookies
4. **Ротация User-Agent**: Пул мобильных UA для обхода WAF
5. **Адаптивные задержки**: Увеличение паузы при ошибках
6. **Расшифровка контента**: Алгоритмы для VIP глав (base64, XOR, zlib)
7. **Fallback механизмы**:
   - Сначала новая система парсеров
   - При ошибке - legacy система

**Архитектура:**
```python
class QidianParser(BaseParser):
    def __init__(self, auth_cookies=None, socks_proxy=None):
        super().__init__("qidian")
        self.session = requests.Session()
        self.socks_proxy = socks_proxy
        self.auth_cookies = auth_cookies
        # Настройка прокси если нужен

    def get_chapter_list(self, book_url):
        # 1. Загружаем каталог
        # 2. Парсим ссылки на главы (BeautifulSoup)
        # 3. Фильтруем служебные главы
        # 4. Возвращаем список

    def get_chapter_content(self, chapter_url):
        # 1. Загружаем страницу главы
        # 2. Проверяем блокировку (lock-mask)
        # 3. Если заблокирована - пробуем расшифровку
        # 4. Извлекаем контент (BeautifulSoup)
        # 5. Очищаем от лишних элементов
```

### 2.2 EPUBParser - Файловый источник

**Особенности:**
- Работает с локальными EPUB файлами
- Использует библиотеку `ebooklib`
- Не требует сети
- Поддержка `start_chapter` и `max_chapters`

---

## 3. 🌐 Анализ czbooks.net

### 3.1 Защита сайта

**Обнаруженная защита:**
- ✅ **Cloudflare Protection**: JavaScript challenge
- ⚠️ **403 Forbidden**: При прямых HTTP запросах
- 🔐 **Turnstile**: Cloudflare CAPTCHA система

**Вывод:** Требуется Selenium с обходом защиты от автоматизации

### 3.2 Типичная структура czbooks.net (на основе аналогов)

**CZBooks.net** - это типичная платформа для китайских веб-новелл. Обычно такие сайты имеют:

#### Страница книги: `https://czbooks.net/n/{book_id}`
```html
<div class="book-info">
    <h1 class="book-title">Название</h1>
    <div class="author">Автор: ...</div>
    <div class="description">...</div>
</div>

<div class="chapter-list" id="chapters">
    <a href="/n/{book_id}/{chapter_id}" class="chapter-item">
        <span class="chapter-number">Глава 1</span>
        <span class="chapter-title">Название</span>
    </a>
    ...
</div>
```

#### Страница главы: `https://czbooks.net/n/{book_id}/{chapter_id}`
```html
<div class="chapter-header">
    <h1 class="chapter-title">Глава 1: Название</h1>
</div>

<div class="chapter-content" id="content">
    <p>Текст главы...</p>
    <p>...</p>
</div>
```

### 3.3 Формат URL

**Предполагаемые паттерны:**
- Книга: `https://czbooks.net/n/{book_id}`
- Глава: `https://czbooks.net/n/{book_id}/{chapter_id}`

**Альтернативные варианты:**
- `https://czbooks.net/novel/{book_id}`
- `https://czbooks.net/book/{book_id}/chapter/{chapter_num}`

### 3.4 Особенности парсинга

1. **Cloudflare Challenge**: Требуется Selenium с обходом `webdriver` detection
2. **Динамическая загрузка**: Возможна подгрузка глав через AJAX
3. **Пагинация глав**: Главы могут быть разделены на страницы
4. **VIP главы**: Возможны платные главы (требуется авторизация)
5. **Анти-бот меры**: Rate limiting, IP блокировки

---

## 4. 📋 План добавления czbooks.net

### 4.1 Необходимые изменения

#### **Шаг 1: Создать CZBooksParser**

Файл: `parsers/sources/czbooks_parser.py`

```python
#!/usr/bin/env python3
"""
Парсер для czbooks.net - платформа китайских веб-новелл
"""
import time
import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'base'))
from base_parser import BaseParser


class CZBooksParser(BaseParser):
    """
    Парсер для czbooks.net
    Поддержка:
    - Selenium для обхода Cloudflare
    - SOCKS прокси
    - Авторизация через cookies
    - VIP главы
    """

    def __init__(self, auth_cookies: str = None, socks_proxy: str = None):
        super().__init__("czbooks")
        self.base_url = "https://czbooks.net"
        self.auth_cookies = auth_cookies
        self.socks_proxy = socks_proxy
        self.driver = None

    def _init_selenium(self):
        """Инициализация Selenium с обходом Cloudflare"""
        if self.driver:
            return

        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')

        # User-Agent для обхода детекции
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        # Обход webdriver detection
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # SOCKS прокси
        if self.socks_proxy:
            chrome_options.add_argument(f'--proxy-server=socks5://{self.socks_proxy}')

        chrome_options.binary_location = '/usr/bin/chromium-browser'
        self.driver = webdriver.Chrome(options=chrome_options)

        # Убираем webdriver флаг
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Устанавливаем cookies если есть
        if self.auth_cookies:
            self.driver.get(self.base_url)
            time.sleep(2)
            for cookie_pair in self.auth_cookies.split(';'):
                if '=' in cookie_pair:
                    name, value = cookie_pair.strip().split('=', 1)
                    self.driver.add_cookie({
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': '.czbooks.net'
                    })

    def _get_page_with_selenium(self, url: str, wait_selector: str = None) -> str:
        """Загрузка страницы через Selenium с обходом Cloudflare"""
        self._init_selenium()

        print(f"🌐 Загрузка через Selenium: {url}")
        self.driver.get(url)

        # Ждем прохождения Cloudflare challenge (до 30 секунд)
        print("⏳ Ожидание прохождения Cloudflare challenge...")
        time.sleep(10)  # Базовая задержка

        # Если указан селектор, ждем его появления
        if wait_selector:
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                )
            except:
                print(f"⚠️ Таймаут ожидания селектора: {wait_selector}")

        return self.driver.page_source

    def get_book_info(self, book_url: str) -> Dict:
        """Получить информацию о книге"""
        html = self._get_page_with_selenium(book_url, '.book-title, h1')
        soup = BeautifulSoup(html, 'html.parser')

        # Извлекаем book_id из URL
        book_id = self._extract_book_id(book_url)

        # Парсим информацию
        title = self._extract_title(soup)
        author = self._extract_author(soup)
        description = self._extract_description(soup)

        return {
            'book_id': book_id,
            'title': title,
            'author': author,
            'description': description,
            'status': 'unknown',
            'genre': 'unknown',
            'total_chapters': 0
        }

    def get_chapter_list(self, book_url: str) -> List[Dict]:
        """Получить список глав"""
        html = self._get_page_with_selenium(book_url, '.chapter-list, #chapters')
        soup = BeautifulSoup(html, 'html.parser')

        # Ищем ссылки на главы
        chapter_links = self._find_chapter_links(soup)

        chapters = []
        for i, link in enumerate(chapter_links, 1):
            href = link.get('href', '')
            title = link.get_text(strip=True)

            # Преобразуем относительные URL
            if href.startswith('/'):
                full_url = f"{self.base_url}{href}"
            else:
                full_url = href

            # Извлекаем chapter_id
            chapter_id = self._extract_chapter_id(full_url)

            chapters.append({
                'number': i,
                'title': title,
                'url': full_url,
                'chapter_id': chapter_id,
                'word_count': 0
            })

        return chapters

    def get_chapter_content(self, chapter_url: str) -> Dict:
        """Получить содержимое главы"""
        html = self._get_page_with_selenium(chapter_url, '.chapter-content, #content')
        soup = BeautifulSoup(html, 'html.parser')

        # Извлекаем заголовок
        title = self._extract_chapter_title(soup)

        # Извлекаем контент
        content = self._extract_chapter_content(soup)

        # Проверяем блокировку
        is_locked = self._check_locked(soup, content)

        return {
            'title': title,
            'content': content,
            'chapter_id': self._extract_chapter_id(chapter_url),
            'word_count': len(content),
            'is_locked': is_locked
        }

    def _extract_book_id(self, url: str) -> str:
        """Извлечь ID книги из URL"""
        match = re.search(r'/n/([^/]+)', url)
        return match.group(1) if match else 'unknown'

    def _extract_chapter_id(self, url: str) -> str:
        """Извлечь ID главы из URL"""
        match = re.search(r'/n/[^/]+/([^/]+)', url)
        return match.group(1) if match else 'unknown'

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлечь название книги"""
        selectors = ['.book-title', 'h1.title', 'h1', '[class*="title"]']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return "Unknown"

    def _extract_author(self, soup: BeautifulSoup) -> str:
        """Извлечь автора"""
        selectors = ['.author', '[class*="author"]', '.writer']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True).replace('作者：', '').replace('Author:', '')
        return "Unknown"

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Извлечь описание"""
        selectors = ['.description', '.synopsis', '[class*="desc"]', '.intro']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return ""

    def _find_chapter_links(self, soup: BeautifulSoup) -> List:
        """Найти ссылки на главы"""
        # Пробуем различные селекторы
        selectors = [
            '.chapter-list a',
            '#chapters a',
            'a[href*="/n/"][href*="/"]',  # Ссылки формата /n/{book_id}/{chapter_id}
            '.toc a'
        ]

        for selector in selectors:
            links = soup.select(selector)
            if links:
                print(f"✅ Найдено глав с селектором '{selector}': {len(links)}")
                return links

        return []

    def _extract_chapter_title(self, soup: BeautifulSoup) -> str:
        """Извлечь заголовок главы"""
        selectors = ['.chapter-title', 'h1', 'h2', '[class*="title"]']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return "Unknown Chapter"

    def _extract_chapter_content(self, soup: BeautifulSoup) -> str:
        """Извлечь содержимое главы"""
        selectors = [
            '.chapter-content',
            '#content',
            '[class*="content"]',
            'article',
            'main'
        ]

        for selector in selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Удаляем лишние элементы
                for unwanted in content_elem.select('script, style, .ad, .navigation'):
                    unwanted.decompose()

                # Извлекаем параграфы
                paragraphs = []
                for p in content_elem.find_all('p'):
                    text = p.get_text(strip=True)
                    if text and len(text) > 10:
                        paragraphs.append(text)

                if paragraphs:
                    return '\n\n'.join(paragraphs)

        return "Content not found"

    def _check_locked(self, soup: BeautifulSoup, content: str) -> bool:
        """Проверить блокировку главы"""
        # Проверяем на маркеры блокировки
        if 'lock' in str(soup).lower() or 'vip' in str(soup).lower():
            return True
        if len(content) < 200:
            return True
        return False

    def close(self):
        """Закрыть Selenium драйвер"""
        if self.driver:
            self.driver.quit()
            self.driver = None
        super().close()
```

#### **Шаг 2: Зарегистрировать парсер в фабрике**

Файл: `parsers/parser_factory.py`

```python
# Импортируем новый парсер
from .sources.czbooks_parser import CZBooksParser

class ParserFactory:
    # Добавляем в реестр
    _parsers: Dict[str, Type[BaseParser]] = {
        'qidian': QidianParser,
        'epub': EPUBParser,
        'czbooks': CZBooksParser,  # ← НОВЫЙ ПАРСЕР
    }

    # Добавляем паттерн URL
    _url_patterns: Dict[str, str] = {
        r'qidian\.com': 'qidian',
        r'\.epub$': 'epub',
        r'czbooks\.net': 'czbooks',  # ← НОВЫЙ ПАТТЕРН
    }
```

#### **Шаг 3: Обновить WebParserService (опционально)**

Файл: `web_app/app/services/parser_service.py`

Текущая реализация уже поддерживает автоматическое определение источника через фабрику. Дополнительных изменений не требуется, но можно добавить специальную обработку для czbooks в `_parse_with_legacy_system()` если нужен fallback.

#### **Шаг 4: Обновить модель Novel (опционально)**

Файл: `web_app/app/models/novel.py`

Добавить `'czbooks'` в список поддерживаемых `source_type` (если есть валидация).

#### **Шаг 5: Обновить UI (опционально)**

Добавить "CZBooks" в выпадающий список источников в форме создания новеллы:

Файл: `web_app/app/templates/novels/...html`

```html
<select name="source_type">
    <option value="novelbins">Novelbins</option>
    <option value="qidian">Qidian</option>
    <option value="epub">EPUB File</option>
    <option value="czbooks">CZBooks</option>  <!-- НОВЫЙ -->
</select>
```

---

## 5. 🧪 Тестирование

### 5.1 Тестовый скрипт

Файл: `test_czbooks_parser.py`

```python
#!/usr/bin/env python3
"""
Тестирование парсера czbooks.net
"""
from parsers import create_parser

def test_czbooks_parser():
    """Тест парсера czbooks"""

    # Тестовая книга
    test_url = "https://czbooks.net/n/ul6pe"

    print("=" * 60)
    print("ТЕСТИРОВАНИЕ CZBOOKS PARSER")
    print("=" * 60)

    # Создаем парсер
    parser = create_parser('czbooks')

    try:
        # Тест 1: Информация о книге
        print("\n1️⃣ Тест: get_book_info()")
        book_info = parser.get_book_info(test_url)
        print(f"   ✅ Название: {book_info['title']}")
        print(f"   ✅ Автор: {book_info['author']}")
        print(f"   ✅ ID: {book_info['book_id']}")

        # Тест 2: Список глав
        print("\n2️⃣ Тест: get_chapter_list()")
        chapters = parser.get_chapter_list(test_url)
        print(f"   ✅ Найдено глав: {len(chapters)}")

        if chapters:
            print(f"\n   Первые 3 главы:")
            for ch in chapters[:3]:
                print(f"      {ch['number']}. {ch['title']}")
                print(f"         URL: {ch['url']}")

        # Тест 3: Содержимое главы
        if chapters:
            print("\n3️⃣ Тест: get_chapter_content()")
            first_chapter = chapters[0]
            content_data = parser.get_chapter_content(first_chapter['url'])

            print(f"   ✅ Заголовок: {content_data['title']}")
            print(f"   ✅ Размер контента: {len(content_data['content'])} символов")
            print(f"   ✅ Заблокирована: {content_data['is_locked']}")
            print(f"\n   Превью контента:")
            print(f"   {content_data['content'][:200]}...")

        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

    finally:
        parser.close()

if __name__ == "__main__":
    test_czbooks_parser()
```

### 5.2 Интеграционный тест с web_app

```python
#!/usr/bin/env python3
"""
Тест интеграции czbooks с web_app
"""
from web_app.app import create_app, db
from web_app.app.models import Novel
from web_app.app.services.parser_service import WebParserService

def test_czbooks_integration():
    """Тест интеграции с web_app"""
    app = create_app('development')

    with app.app_context():
        # Создаем тестовую новеллу
        novel = Novel(
            title="Test CZBooks Novel",
            source_type="czbooks",
            source_url="https://czbooks.net/n/ul6pe",
            config={'max_chapters': 5}
        )
        db.session.add(novel)
        db.session.commit()

        # Парсим
        parser_service = WebParserService()
        chapters = parser_service.parse_novel_chapters(novel)

        print(f"✅ Найдено глав: {len(chapters)}")

        # Парсим первую главу
        if chapters:
            content = parser_service.parse_chapter_content(
                chapters[0]['url'],
                chapters[0]['number'],
                novel
            )
            print(f"✅ Контент первой главы: {len(content)} символов")

        # Удаляем тестовую новеллу
        db.session.delete(novel)
        db.session.commit()

if __name__ == "__main__":
    test_czbooks_integration()
```

---

## 6. 🚀 Развертывание

### 6.1 Установка зависимостей

```bash
# Selenium для Chrome
pip install selenium

# Проверка наличия ChromeDriver
which chromedriver

# Если нет - установить
sudo apt-get install chromium-chromedriver
```

### 6.2 Миграция БД (если нужна)

```bash
cd web_app
flask db migrate -m "Add czbooks support"
flask db upgrade
```

### 6.3 Запуск тестов

```bash
# Тест парсера
python test_czbooks_parser.py

# Интеграционный тест
python test_czbooks_integration.py
```

---

## 7. ⚠️ Особенности и проблемы

### 7.1 Cloudflare Protection

**Проблема:** Cloudflare JavaScript challenge блокирует автоматический доступ

**Решения:**
1. ✅ **Selenium с антидетектом** (рекомендуется)
   - Обход webdriver detection
   - Имитация человеческого поведения
   - Случайные задержки

2. **Использование cookies**
   - Получить cookies из браузера после ручного прохождения challenge
   - Передать в `auth_cookies`

3. **Прокси ротация**
   - Использовать пул SOCKS прокси
   - Ротация при блокировках

4. **Сторонние сервисы**
   - FlareSolverr (Docker сервис для обхода Cloudflare)
   - Scraperapi / ScrapingBee (платные API)

### 7.2 Rate Limiting

**Рекомендации:**
- Добавить задержку между запросами (3-5 секунд)
- Использовать экспоненциальный backoff при ошибках
- Ограничить параллельные запросы

### 7.3 Изменения структуры сайта

**Проблема:** Селекторы CSS могут измениться

**Решения:**
- Использовать множественные селекторы-fallback
- Регулярные проверки работоспособности
- Логирование ошибок для быстрого обнаружения

---

## 8. 📊 Оценка трудозатрат

| Задача | Время | Сложность |
|--------|-------|-----------|
| Создание CZBooksParser | 4-6 часов | Средняя |
| Регистрация в фабрике | 30 минут | Низкая |
| Обход Cloudflare | 2-4 часа | Высокая |
| Тестирование | 2-3 часа | Средняя |
| UI обновления | 1 час | Низкая |
| Документация | 1 час | Низкая |
| **ИТОГО** | **10-15 часов** | - |

---

## 9. 🔧 Дополнительные улучшения

### 9.1 Расширенная поддержка

1. **API Mode**: Если czbooks.net имеет API, использовать его вместо парсинга
2. **Кэширование**: Redis кэш для списков глав
3. **Асинхронность**: Использовать aiohttp для параллельной загрузки
4. **Прогресс-бар**: WebSocket для live обновлений прогресса парсинга

### 9.2 Мониторинг

1. **Алерты**: Уведомления при блокировке IP
2. **Метрики**: Grafana/Prometheus для мониторинга успешности
3. **Логирование**: Детальные логи для отладки

---

## 10. 📝 Итоговый чеклист

- [ ] Создать `parsers/sources/czbooks_parser.py`
- [ ] Добавить импорт в `parsers/sources/__init__.py`
- [ ] Зарегистрировать в `parsers/parser_factory.py`
- [ ] Создать тестовый скрипт `test_czbooks_parser.py`
- [ ] Протестировать основные функции
- [ ] Обновить UI (добавить czbooks в select)
- [ ] Создать миграцию БД (если нужна)
- [ ] Обновить документацию (CLAUDE.md)
- [ ] Провести интеграционное тестирование
- [ ] Deploy на production

---

## 11. 🔗 Полезные ссылки

- **Selenium Docs**: https://selenium-python.readthedocs.io/
- **BeautifulSoup Docs**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- **Cloudflare Bypass**: https://github.com/FlareSolverr/FlareSolverr
- **Undetected ChromeDriver**: https://github.com/ultrafunkamsterdam/undetected-chromedriver

---

**Дата создания:** 2025-10-13
**Автор:** Claude Code Assistant
**Версия:** 1.0
