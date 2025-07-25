"""
Сервис парсинга глав для веб-приложения
"""
import time
import re
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from app.models import Novel, Chapter, Task
from app import db
from app.services.settings_service import SettingsService
from app.services.log_service import LogService

# Настраиваем логгер
logger = logging.getLogger(__name__)


class WebParserService:
    """Сервис парсинга для веб-приложения"""

    def __init__(self):
        self.driver = None
        self.wait = None

    def setup_driver(self):
        """Настройка Chrome драйвера"""
        chrome_options = Options()
        # chrome_options.add_argument('--headless')  # Временно отключаем для диагностики
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.binary_location = '/usr/bin/chromium-browser'
        chrome_options.add_argument('--incognito')  # Используем режим инкогнито
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-features=TranslateUI')
        chrome_options.add_argument('--disable-ipc-flooding-protection')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 30)  # Увеличиваем таймаут

    def cleanup_driver(self):
        """Очистка драйвера"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None

    def extract_chapter_number(self, url: str) -> int:
        """Извлечение номера главы из URL"""
        match = re.search(r'/chapter/(\d+)', url)
        return int(match.group(1)) if match else 0

    def parse_novel_chapters(self, novel: Novel) -> List[dict]:
        """Парсинг всех глав новеллы с помощью requests (новая структура сайта)"""
        LogService.log_info(f"Парсинг новеллы: {novel.title}", novel_id=novel.id)
        
        # Исправляем URL - добавляем слеш в конце если его нет
        novel_url = novel.source_url
        if not novel_url.endswith('/'):
            novel_url += '/'
        
        LogService.log_info(f"URL: {novel_url}", novel_id=novel.id)

        try:
            # Загружаем страницу с помощью requests
            LogService.log_info("Загрузка страницы новеллы...", novel_id=novel.id)
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(novel_url, headers=headers, timeout=30)
            response.raise_for_status()
            LogService.log_info("Страница загружена", novel_id=novel.id)

            # Парсим HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем все ссылки на главы
            LogService.log_info("Поиск ссылок на главы...", novel_id=novel.id)
            chapter_links = soup.find_all('a', href=re.compile(r'/chapter/\d+'))
            LogService.log_info(f"Найдено ссылок на главы: {len(chapter_links)}", novel_id=novel.id)

            all_chapters = []
            # Используем настройки из конфигурации новеллы
            max_chapters = novel.config.get('max_chapters', 10) if novel.config else 10

            # Собираем все главы сначала
            temp_chapters = []
            for link in chapter_links:
                href = link.get('href')
                title = link.text.strip()
                chapter_num = self.extract_chapter_number(href)

                if chapter_num > 0:
                    # Преобразуем относительный URL в абсолютный
                    if href.startswith('/'):
                        full_url = f"https://novelbins.com{href}"
                    else:
                        full_url = href
                        
                    temp_chapters.append({
                        'url': full_url,
                        'title': title,
                        'number': chapter_num
                    })

            # Сортируем по номеру главы
            temp_chapters.sort(key=lambda x: x['number'])
            
            # Берем только первые max_chapters глав
            all_chapters = temp_chapters[:max_chapters]
            LogService.log_info(f"Выбрано первых {len(all_chapters)} глав из {len(temp_chapters)} найденных", novel_id=novel.id)

            # Сортируем по номеру
            all_chapters.sort(key=lambda x: x['number'])
            LogService.log_info(f"Всего найдено глав: {len(all_chapters)}", novel_id=novel.id)

            return all_chapters

        except Exception as e:
            LogService.log_error(f"Ошибка при парсинге глав: {e}", novel_id=novel.id)
            return []

    def parse_chapter_content(self, chapter_url: str, chapter_number: int) -> Optional[str]:
        """Парсинг содержимого главы с помощью requests"""
        LogService.log_info(f"Загрузка главы {chapter_number}: {chapter_url}")

        try:
            # Загружаем страницу главы
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(chapter_url, headers=headers, timeout=30)
            response.raise_for_status()

            # Парсим HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем контейнер с контентом
            content_div = soup.find('div', class_='page-content-wrapper')
            if not content_div:
                LogService.log_error("Контейнер контента не найден")
                return None

            # Удаляем лишние элементы
            for element in content_div.find_all(['script', 'style', 'nav', 'button']):
                element.decompose()

            # Извлекаем параграфы
            paragraphs = []
            p_elements = content_div.find_all('p')

            for p in p_elements:
                text = p.get_text().strip()
                if text and len(text) > 30 and not text.startswith('Chapter'):
                    paragraphs.append(text)

            # Если мало параграфов, берём весь текст
            if len(paragraphs) < 5:
                text = content_div.get_text()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                paragraphs = [line for line in lines if len(line) > 50]

            content = '\n\n'.join(paragraphs)
            word_count = len(content.split())

            LogService.log_info(f"Извлечено {len(paragraphs)} параграфов, {word_count} слов")

            return content

        except Exception as e:
            LogService.log_error(f"Ошибка при загрузке главы {chapter_number}: {e}")
            return None

    def parse_novel(self, novel_id: int, task_id: int = None) -> bool:
        """Полный парсинг новеллы"""
        try:
            # Получаем новеллу
            novel = Novel.query.get(novel_id)
            if not novel:
                LogService.log_error(f"Новелла {novel_id} не найдена", novel_id=novel_id, task_id=task_id)
                return False

            # Получаем задачу
            if task_id:
                task = Task.query.get(task_id)
            else:
                task = Task.query.filter_by(novel_id=novel_id, task_type='parse').first()
            
            if task:
                task.status = 'running'
                db.session.commit()

            LogService.log_info(f"Начинаем парсинг новеллы: {novel.title}", novel_id=novel_id, task_id=task_id)
            print(f"🚀 Начинаем парсинг новеллы: {novel.title}")
            print(f"📊 Задача #{task_id}: Парсинг новеллы '{novel.title}'")

            # Парсим все главы
            LogService.log_info("Начинаем парсинг списка глав...", novel_id=novel_id, task_id=task_id)
            print(f"🔍 Поиск глав для новеллы '{novel.title}'...")
            chapters_data = self.parse_novel_chapters(novel)
            if not chapters_data:
                LogService.log_error("Не удалось получить список глав", novel_id=novel_id, task_id=task_id)
                return False

            LogService.log_info(f"Найдено глав для парсинга: {len(chapters_data)}", novel_id=novel_id, task_id=task_id)
            print(f"📚 Найдено {len(chapters_data)} глав для парсинга")

            # Парсим содержимое каждой главы
            success_count = 0
            for i, chapter_data in enumerate(chapters_data):
                LogService.log_info(f"Обработка главы {i+1}/{len(chapters_data)}: {chapter_data['title']}", 
                                  novel_id=novel_id, task_id=task_id)
                print(f"📖 Обработка главы {i+1}/{len(chapters_data)}: {chapter_data['title']}")

                # Проверяем, не существует ли уже активная глава
                existing_chapter = Chapter.query.filter_by(
                    novel_id=novel_id,
                    chapter_number=chapter_data['number'],
                    is_active=True
                ).first()

                if existing_chapter:
                    LogService.log_info(f"Глава {chapter_data['number']} уже существует и активна", 
                                      novel_id=novel_id, task_id=task_id)
                    continue

                # Парсим содержимое
                LogService.log_info(f"Загрузка содержимого главы {chapter_data['number']}...", 
                                  novel_id=novel_id, task_id=task_id)
                content = self.parse_chapter_content(chapter_data['url'], chapter_data['number'])
                if not content:
                    LogService.log_warning(f"Не удалось загрузить содержимое главы {chapter_data['number']}", 
                                         novel_id=novel_id, task_id=task_id)
                    continue

                # Создаем главу в БД
                chapter = Chapter(
                    novel_id=novel_id,
                    chapter_number=chapter_data['number'],
                    original_title=chapter_data['title'],
                    url=chapter_data['url'],
                    original_text=content,
                    status='parsed'
                )
                db.session.add(chapter)
                success_count += 1
                LogService.log_info(f"Глава {chapter_data['number']} сохранена в БД", 
                                  novel_id=novel_id, task_id=task_id, chapter_id=chapter.id)

                # Обновляем прогресс
                if task:
                    progress = int((i + 1) / len(chapters_data) * 100)
                    task.progress = progress
                    db.session.commit()

                # Задержка между запросами
                delay = novel.config.get('request_delay', 1.0) if novel.config else 1.0
                if delay > 0:
                    LogService.log_info(f"Пауза {delay} секунд...", novel_id=novel_id, task_id=task_id)
                    time.sleep(delay)

            # Обновляем статистику новеллы
            novel.total_chapters = len(chapters_data)
            novel.parsed_chapters = success_count
            # Обновляем статус новеллы
            if success_count > 0:
                novel.status = 'parsed'
            db.session.commit()

            # Завершаем задачу
            if task:
                task.status = 'completed'
                task.progress = 100
                db.session.commit()

            LogService.log_info(f"Парсинг завершен: {success_count}/{len(chapters_data)} глав обработано", 
                              novel_id=novel_id, task_id=task_id)
            return True

        except Exception as e:
            LogService.log_error(f"Ошибка при парсинге новеллы: {e}", novel_id=novel_id, task_id=task_id)
            
            # Обновляем статус задачи
            task = Task.query.filter_by(novel_id=novel_id, task_type='parse').first()
            if task:
                task.status = 'failed'
                db.session.commit()

            return False 