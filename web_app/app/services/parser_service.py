"""
Сервис парсинга глав для веб-приложения
"""
import time
import re
from typing import List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from app.models import Novel, Chapter, Task
from app import db
from app.services.settings_service import SettingsService


class WebParserService:
    """Сервис парсинга для веб-приложения"""

    def __init__(self):
        self.driver = None
        self.wait = None

    def setup_driver(self):
        """Настройка драйвера Chrome"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')
        chrome_options.binary_location = '/usr/bin/chromium-browser'

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

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
        """Парсинг всех глав новеллы"""
        print(f"🔍 Парсинг новеллы: {novel.title}")
        print(f"📖 URL: {novel.source_url}")

        try:
            print("🔧 Настройка драйвера...")
            self.setup_driver()
            print("✅ Драйвер настроен")
            
            # Загружаем страницу новеллы
            print("📄 Загрузка страницы новеллы...")
            self.driver.get(novel.source_url)
            print("✅ Страница загружена")

            # Ждём загрузки вкладок (с таймаутом)
            try:
                print("🔍 Поиск вкладок...")
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.nav-tabs a.ch')))
                print("✅ Вкладки найдены")

                # Находим все вкладки
                tabs = self.driver.find_elements(By.CSS_SELECTOR, 'ul.nav-tabs a.ch')
                print(f"✅ Найдено вкладок: {len(tabs)}")
            except Exception as e:
                print(f"⚠️ Вкладки не найдены: {e}")
                print("📄 Текущий HTML страницы:")
                print(self.driver.page_source[:500] + "...")
                return []

            all_chapters = []
            # Используем настройки из конфигурации новеллы
            max_chapters = novel.config.get('max_chapters', 10) if novel.config else 10

            # Проходим по каждой вкладке
            for i, tab in enumerate(tabs):
                if len(all_chapters) >= max_chapters:
                    print(f"⚠️ Достигнут лимит глав: {max_chapters}")
                    break

                tab_text = tab.text
                print(f"\n📑 Загрузка вкладки {i+1}/{len(tabs)}: {tab_text}")

                # Кликаем на вкладку
                tab.click()
                time.sleep(1)

                # Находим все ссылки на главы
                chapter_links = self.driver.find_elements(By.CSS_SELECTOR, '#chapter-content a[href*="/chapter/"]')

                new_chapters = 0
                for link in chapter_links:
                    if len(all_chapters) >= max_chapters:
                        break

                    href = link.get_attribute('href')
                    title = link.text.strip()
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

        except Exception as e:
            print(f"❌ Ошибка при парсинге глав: {e}")
            return []
        finally:
            self.cleanup_driver()

    def parse_chapter_content(self, chapter_url: str, chapter_number: int) -> Optional[str]:
        """Парсинг содержимого главы"""
        print(f"📖 Загрузка главы {chapter_number}: {chapter_url}")

        try:
            self.setup_driver()
            self.driver.get(chapter_url)

            # Ждём загрузки контента
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.page-content-wrapper')))

            # Извлекаем текст главы
            content_element = self.driver.find_element(By.CSS_SELECTOR, 'div.page-content-wrapper')
            chapter_text = content_element.text

            if not chapter_text.strip():
                print(f"⚠️ Пустой контент для главы {chapter_number}")
                return None

            print(f"✅ Глава {chapter_number} загружена: {len(chapter_text)} символов")
            return chapter_text

        except Exception as e:
            print(f"❌ Ошибка при загрузке главы {chapter_number}: {e}")
            return None
        finally:
            self.cleanup_driver()

    def parse_novel(self, novel_id: int, task_id: int = None) -> bool:
        """Полный парсинг новеллы"""
        try:
            # Получаем новеллу
            novel = Novel.query.get(novel_id)
            if not novel:
                print(f"❌ Новелла {novel_id} не найдена")
                return False

            # Получаем задачу
            if task_id:
                task = Task.query.get(task_id)
            else:
                task = Task.query.filter_by(novel_id=novel_id, task_type='parse').first()
            
            if task:
                task.status = 'running'
                db.session.commit()

            print(f"🚀 Начинаем парсинг новеллы: {novel.title}")

            # Парсим все главы
            chapters_data = self.parse_novel_chapters(novel)
            if not chapters_data:
                print("❌ Не удалось получить список глав")
                return False

            # Парсим содержимое каждой главы
            success_count = 0
            for i, chapter_data in enumerate(chapters_data):
                print(f"\n📝 Обработка главы {i+1}/{len(chapters_data)}: {chapter_data['title']}")

                # Проверяем, не существует ли уже активная глава
                existing_chapter = Chapter.query.filter_by(
                    novel_id=novel_id,
                    chapter_number=chapter_data['number'],
                    is_active=True
                ).first()

                if existing_chapter:
                    print(f"⏭️ Глава {chapter_data['number']} уже существует и активна")
                    continue

                # Парсим содержимое
                content = self.parse_chapter_content(chapter_data['url'], chapter_data['number'])
                if not content:
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

                # Обновляем прогресс
                if task:
                    progress = int((i + 1) / len(chapters_data) * 100)
                    task.progress = progress
                    db.session.commit()

                # Задержка между запросами
                delay = novel.config.get('request_delay', 1.0) if novel.config else 1.0
                if delay > 0:
                    time.sleep(delay)

            # Обновляем статистику новеллы
            novel.total_chapters = len(chapters_data)
            novel.parsed_chapters = success_count
            db.session.commit()

            # Завершаем задачу
            if task:
                task.status = 'completed'
                task.progress = 100
                db.session.commit()

            print(f"\n✅ Парсинг завершен: {success_count}/{len(chapters_data)} глав обработано")
            return True

        except Exception as e:
            print(f"❌ Ошибка при парсинге новеллы: {e}")
            
            # Обновляем статус задачи
            task = Task.query.filter_by(novel_id=novel_id, task_type='parse').first()
            if task:
                task.status = 'failed'
                db.session.commit()

            return False 