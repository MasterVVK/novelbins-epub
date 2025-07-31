"""
Сервис парсинга глав для веб-приложения
Обновлен для использования новой системы парсеров
"""
import time
import re
import logging
import requests
import sys
import os
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

# Добавляем путь к новой системе парсеров
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

try:
    from parsers import create_parser_from_url, detect_source, get_available_sources
    PARSERS_AVAILABLE = True
    LogService.log_info("✅ Новая система парсеров загружена успешно")
except ImportError as e:
    LogService.log_warning(f"⚠️ Новая система парсеров недоступна: {e}")
    PARSERS_AVAILABLE = False

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
        """Парсинг всех глав новеллы с использованием новой системы парсеров"""
        LogService.log_info(f"🚀 Начинаем парсинг новеллы: {novel.title}", novel_id=novel.id)
        
        novel_url = novel.source_url
        LogService.log_info(f"📖 URL: {novel_url}", novel_id=novel.id)
        
        # Пробуем использовать новую систему парсеров
        if PARSERS_AVAILABLE:
            return self._parse_with_new_system(novel, novel_url)
        else:
            LogService.log_warning("⚠️ Используется устаревший парсер", novel_id=novel.id)
            return self._parse_with_legacy_system(novel, novel_url)

    def _parse_with_new_system(self, novel: Novel, novel_url: str) -> List[dict]:
        """Парсинг с использованием новой системы парсеров"""
        try:
            LogService.log_info("🔍 Определение источника...", novel_id=novel.id)
            
            # Определяем источник
            detected_source = detect_source(novel_url)
            source_type = novel.source_type if novel.source_type else detected_source
            
            LogService.log_info(f"📚 Источник: {source_type} (определен: {detected_source})", novel_id=novel.id)
            
            # Создаем парсер
            parser = create_parser_from_url(novel_url)
            if not parser:
                LogService.log_error(f"❌ Не удалось создать парсер для {source_type}", novel_id=novel.id)
                return self._parse_with_legacy_system(novel, novel_url)
            
            LogService.log_info(f"✅ Парсер создан: {parser.source_name}", novel_id=novel.id)
            
            # Получаем список глав
            LogService.log_info("📖 Получение списка глав...", novel_id=novel.id)
            chapters = parser.get_chapter_list(novel_url)
            
            if not chapters:
                LogService.log_warning("⚠️ Новая система не нашла главы, переключаемся на fallback", novel_id=novel.id)
                return self._parse_with_legacy_system(novel, novel_url)
            
            LogService.log_info(f"📑 Найдено глав: {len(chapters)}", novel_id=novel.id)
            
            # Применяем ограничение по количеству глав
            all_chapters_enabled = novel.config.get('all_chapters', False) if novel.config else False
            
            if all_chapters_enabled:
                limited_chapters = chapters
                LogService.log_info(f"📊 Выбрано все главы: {len(chapters)} глав", novel_id=novel.id)
            else:
                max_chapters = novel.config.get('max_chapters', 10) if novel.config else 10
                limited_chapters = chapters[:max_chapters]
                LogService.log_info(f"📊 Выбрано для обработки: {len(limited_chapters)} из {len(chapters)} глав", novel_id=novel.id)
            
            # Конвертируем в формат, ожидаемый веб-приложением
            result_chapters = []
            for i, chapter in enumerate(limited_chapters, 1):
                result_chapters.append({
                    'url': chapter['url'],
                    'title': chapter['title'],
                    'number': chapter.get('number', i)
                })
            
            # Закрываем парсер
            parser.close()
            
            LogService.log_info(f"✅ Парсинг завершен успешно: {len(result_chapters)} глав", novel_id=novel.id)
            return result_chapters
            
        except Exception as e:
            LogService.log_error(f"❌ Ошибка в новой системе парсеров: {e}", novel_id=novel.id)
            LogService.log_info("🔄 Переключаемся на старую систему парсинга", novel_id=novel.id)
            # Откат к старой системе при ошибке
            return self._parse_with_legacy_system(novel, novel_url)

    def _parse_with_legacy_system(self, novel: Novel, novel_url: str) -> List[dict]:
        """Устаревший парсер для обратной совместимости"""
        try:
            # Исправляем URL - добавляем слеш в конце если его нет
            if not novel_url.endswith('/'):
                novel_url += '/'
            
            # Для Qidian используем страницу каталога, для других - основную страницу
            if 'qidian.com' in novel_url:
                # Извлекаем ID книги из URL Qidian
                import re
                book_id_match = re.search(r'/book/(\d+)/?', novel_url)
                if book_id_match:
                    book_id = book_id_match.group(1)
                    catalog_url = f"https://m.qidian.com/book/{book_id}/catalog"
                    LogService.log_info(f"Загрузка каталога Qidian: {catalog_url}", novel_id=novel.id)
                else:
                    catalog_url = novel_url
                    LogService.log_info("Загрузка страницы новеллы...", novel_id=novel.id)
            else:
                catalog_url = novel_url
                LogService.log_info("Загрузка страницы новеллы...", novel_id=novel.id)
            
            # Используем мобильный User-Agent для Qidian
            if 'qidian.com' in catalog_url:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                }
            else:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                
            response = requests.get(catalog_url, headers=headers, timeout=30)
            response.raise_for_status()
            LogService.log_info("Страница загружена", novel_id=novel.id)

            # Парсим HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем ссылки на главы в зависимости от сайта
            LogService.log_info("Поиск ссылок на главы...", novel_id=novel.id)
            
            if 'qidian.com' in catalog_url:
                # Для Qidian используем специальные селекторы
                chapter_links = soup.select('a[href*="/chapter/"]')
            else:
                # Для других сайтов используем старый метод
                chapter_links = soup.find_all('a', href=re.compile(r'/chapter/\d+'))
                
            LogService.log_info(f"Найдено ссылок на главы: {len(chapter_links)}", novel_id=novel.id)

            all_chapters = []
            # Используем настройки из конфигурации новеллы
            all_chapters_enabled = novel.config.get('all_chapters', False) if novel.config else False
            max_chapters = novel.config.get('max_chapters', 10) if novel.config else 10

            # Собираем все главы сначала
            temp_chapters = []
            for i, link in enumerate(chapter_links):
                href = link.get('href')
                title = link.text.strip()
                
                if 'qidian.com' in catalog_url:
                    # Для Qidian специальная обработка
                    if href and title:
                        # Преобразуем относительные URL в абсолютные
                        if href.startswith('//'):
                            full_url = f"https:{href}"
                        elif href.startswith('/'):
                            full_url = f"https://m.qidian.com{href}"
                        else:
                            full_url = href
                            
                        # Фильтруем служебные главы
                        if self._is_qidian_story_chapter(title):
                            temp_chapters.append({
                                'url': full_url,
                                'title': title,
                                'number': i + 1  # Просто порядковый номер
                            })
                else:
                    # Для других сайтов старая логика
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
            
            # Применяем ограничение по количеству глав
            if all_chapters_enabled:
                all_chapters = temp_chapters
                LogService.log_info(f"Выбрано все главы: {len(all_chapters)} глав", novel_id=novel.id)
            else:
                all_chapters = temp_chapters[:max_chapters]
                LogService.log_info(f"Выбрано первых {len(all_chapters)} глав из {len(temp_chapters)} найденных", novel_id=novel.id)

            # Сортируем по номеру
            all_chapters.sort(key=lambda x: x['number'])
            LogService.log_info(f"Всего найдено глав: {len(all_chapters)}", novel_id=novel.id)

            return all_chapters

        except Exception as e:
            LogService.log_error(f"Ошибка при парсинге глав: {e}", novel_id=novel.id)
            return []
    
    def _is_qidian_story_chapter(self, title: str) -> bool:
        """
        Проверяет, является ли глава частью основной истории для Qidian
        """
        if not title or len(title.strip()) < 3:
            return False
            
        # Главы истории обычно начинаются с "第" (глава)
        if title.startswith('第') and ('章' in title or '回' in title):
            return True
            
        # Служебные ключевые слова
        service_keywords = [
            '新书', '发布', '通知', '公告', '说明', '抽奖', '活动',
            '教程', '外传', '番外', '感言', '推荐', '骗子', '冒充',
            '海量', 'iPad', '起点币', '经验', '推荐票',
            '2022-', '2023-', '2024-', '2025-',
            '作家入驻', '即更即看', '还有番外'
        ]
        
        # Проверяем на наличие служебных ключевых слов
        for keyword in service_keywords:
            if keyword in title:
                return False
                
        # По умолчанию считаем главой истории
        return True

    def parse_chapter_content(self, chapter_url: str, chapter_number: int) -> Optional[str]:
        """Парсинг содержимого главы с использованием новой системы парсеров"""
        LogService.log_info(f"📄 Загрузка главы {chapter_number}: {chapter_url}")
        
        # Пробуем использовать новую систему парсеров
        if PARSERS_AVAILABLE:
            return self._parse_chapter_with_new_system(chapter_url, chapter_number)
        else:
            LogService.log_warning("⚠️ Используется устаревший парсер для главы", chapter_id=chapter_number)
            return self._parse_chapter_with_legacy_system(chapter_url, chapter_number)

    def _parse_chapter_with_new_system(self, chapter_url: str, chapter_number: int) -> Optional[str]:
        """Парсинг содержимого главы с новой системой"""
        try:
            # Создаем парсер для URL главы
            parser = create_parser_from_url(chapter_url)
            if not parser:
                LogService.log_warning(f"⚠️ Не удалось создать парсер для главы {chapter_number}, используем legacy", chapter_id=chapter_number)
                return self._parse_chapter_with_legacy_system(chapter_url, chapter_number)
            
            # Получаем содержимое главы
            chapter_data = parser.get_chapter_content(chapter_url)
            if not chapter_data or not chapter_data.get('content'):
                LogService.log_error(f"❌ Пустое содержимое главы {chapter_number}", chapter_id=chapter_number)
                parser.close()
                return None
            
            content = chapter_data['content']
            LogService.log_info(f"✅ Глава {chapter_number} загружена: {len(content)} символов", chapter_id=chapter_number)
            
            # Закрываем парсер
            parser.close()
            
            return content
            
        except Exception as e:
            LogService.log_error(f"❌ Ошибка парсинга главы {chapter_number} новой системой: {e}", chapter_id=chapter_number)
            # Откат к старой системе
            return self._parse_chapter_with_legacy_system(chapter_url, chapter_number)

    def _parse_chapter_with_legacy_system(self, chapter_url: str, chapter_number: int) -> Optional[str]:
        """Устаревший парсер для содержимого глав"""

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

                # Проверяем, не существует ли уже глава
                existing_chapter = Chapter.query.filter_by(
                    novel_id=novel_id,
                    chapter_number=chapter_data['number']
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