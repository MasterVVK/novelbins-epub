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
    from parsers import create_parser, create_parser_from_url, detect_source, get_available_sources
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
            LogService.log_info("✅ Новая система парсеров доступна", novel_id=novel.id)
            return self._parse_with_new_system(novel, novel_url)
        else:
            LogService.log_warning("⚠️ Используется устаревший парсер", novel_id=novel.id)
            return self._parse_with_legacy_system(novel, novel_url)

    def _parse_with_new_system(self, novel: Novel, novel_url: str) -> List[dict]:
        """Парсинг с использованием новой системы парсеров"""
        try:
            LogService.log_info("🚀 Начинаем парсинг новой системой", novel_id=novel.id)
            LogService.log_info("🔍 Определение источника...", novel_id=novel.id)
            
            # Определяем источник
            detected_source = detect_source(novel_url)
            source_type = novel.source_type if novel.source_type else detected_source
            
            LogService.log_info(f"📚 Источник: {source_type} (определен: {detected_source})", novel_id=novel.id)
            
            # Получаем настройки авторизации и прокси
            auth_cookies = None
            socks_proxy = None
            
            if novel.is_auth_enabled():
                auth_cookies = novel.get_auth_cookies()
                LogService.log_info(f"🔐 Используем авторизацию: {len(auth_cookies)} символов", novel_id=novel.id)
            
            if novel.is_proxy_enabled():
                socks_proxy = novel.get_socks_proxy()
                LogService.log_info(f"🌐 Используем SOCKS прокси: {socks_proxy}", novel_id=novel.id)
            
            # Создаем парсер с настройками
            if source_type == 'epub':
                # Специальная обработка для EPUB файлов
                epub_path = novel.get_epub_file_path()
                if not epub_path:
                    LogService.log_error(f"❌ Для EPUB источника не указан путь к файлу", novel_id=novel.id)
                    return []
                
                # Определяем максимум глав для EPUB
                all_chapters_enabled = novel.config.get('all_chapters', False) if novel.config else False
                max_chapters = None if all_chapters_enabled else (novel.config.get('max_chapters', 10) if novel.config else 10)
                
                # Получаем начальную главу
                start_chapter = novel.config.get('start_chapter', 1) if novel.config else 1
                LogService.log_info(f"📖 Настройки EPUB: начальная глава = {start_chapter}, макс. глав = {max_chapters or 'все'}", novel_id=novel.id)
                
                parser = create_parser('epub', epub_path=epub_path, max_chapters=max_chapters, start_chapter=start_chapter)
                novel_url = epub_path  # Используем путь к файлу как URL
            else:
                parser = create_parser_from_url(novel_url, auth_cookies=auth_cookies, socks_proxy=socks_proxy)
            
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
                if 'url' not in chapter:
                    LogService.log_error(f"⚠️ Глава не содержит URL: {chapter}", novel_id=novel.id)
                    chapter['url'] = chapter.get('chapter_id', f"chapter_{i}")
                result_chapters.append({
                    'url': chapter['url'],
                    'title': chapter['title'],
                    'number': chapter.get('number', i)
                })
                LogService.log_info(f"  -> Глава для сохранения: #{chapter.get('number', i)} - {chapter['title'][:50]}...", novel_id=novel.id)
            
            # Закрываем парсер
            parser.close()
            
            LogService.log_info(f"✅ Парсинг завершен успешно: {len(result_chapters)} глав", novel_id=novel.id)
            return result_chapters
            
        except Exception as e:
            import traceback
            LogService.log_error(f"❌ Ошибка в новой системе парсеров: {e}", novel_id=novel.id)
            LogService.log_error(f"Полный стек ошибки: {traceback.format_exc()}", novel_id=novel.id)
            LogService.log_info("🔄 Переключаемся на старую систему парсинга", novel_id=novel.id)
            # Откат к старой системе при ошибке
            return self._parse_with_legacy_system(novel, novel_url)

    def _parse_with_legacy_system(self, novel: Novel, novel_url: str) -> List[dict]:
        """Устаревший парсер для обратной совместимости"""
        try:
            # Специальная обработка для EPUB источников
            if novel.is_epub_source():
                LogService.log_info("📖 Обработка EPUB файла в legacy системе", novel_id=novel.id)
                try:
                    from parsers.sources.epub_parser import EPUBParser
                    epub_path = novel.get_epub_file_path()
                    
                    if not epub_path or not os.path.exists(epub_path):
                        LogService.log_error(f"EPUB файл не найден: {epub_path}", novel_id=novel.id)
                        return []
                    
                    # Определяем максимум глав
                    all_chapters_enabled = novel.config.get('all_chapters', False) if novel.config else False
                    max_chapters = None if all_chapters_enabled else (novel.config.get('max_chapters', 10) if novel.config else 10)
                    
                    # Получаем начальную главу
                    start_chapter = novel.config.get('start_chapter', 1) if novel.config else 1
                    LogService.log_info(f"📖 Настройки EPUB (legacy): начальная глава = {start_chapter}, макс. глав = {max_chapters or 'все'}", novel_id=novel.id)
                    
                    LogService.log_info(f"📖 [Legacy] Создаем EPUB парсер: start_chapter={start_chapter}, max_chapters={max_chapters}", novel_id=novel.id)
                    parser = EPUBParser(epub_path=epub_path, max_chapters=max_chapters, start_chapter=start_chapter)
                    if not parser.load_epub(epub_path):
                        LogService.log_error("Не удалось загрузить EPUB файл", novel_id=novel.id)
                        return []
                    
                    chapters = parser.get_chapter_list()
                    LogService.log_info(f"Извлечено глав из EPUB: {len(chapters)}" + 
                                       (f" (лимит: {max_chapters})" if max_chapters else " (все главы)"), 
                                       novel_id=novel.id)
                    
                    # Конвертируем в формат, ожидаемый веб-приложением
                    result_chapters = []
                    for i, chapter in enumerate(chapters, 1):
                        result_chapters.append({
                            'url': f"chapter_{chapter['number']}",  # Используем ID главы как URL
                            'title': chapter['title'],
                            'number': chapter['number']
                        })
                        LogService.log_info(f"  -> [Legacy] Глава для сохранения: #{chapter['number']} - {chapter['title'][:50]}...", novel_id=novel.id)
                    
                    parser.close()
                    return result_chapters
                    
                except Exception as e:
                    LogService.log_error(f"Ошибка обработки EPUB в legacy системе: {e}", novel_id=novel.id)
                    return []
            
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

    def parse_chapter_content(self, chapter_url: str, chapter_number: int, novel: Novel = None) -> Optional[str]:
        """Парсинг содержимого главы с использованием новой системы парсеров"""
        LogService.log_info(f"📄 Загрузка главы {chapter_number}: {chapter_url}")
        
        # Если новелла не передана, пытаемся найти её
        if not novel:
            # Для EPUB глав ищем по source_type
            if chapter_url.startswith('chapter_'):
                novel = Novel.query.filter_by(source_type='epub').first()
            else:
                # Для веб-источников ищем по source_url
                novel = Novel.query.filter_by(source_url=chapter_url).first()

        # Пробуем использовать новую систему парсеров
        if PARSERS_AVAILABLE:
            return self._parse_chapter_with_new_system(chapter_url, chapter_number, novel)
        else:
            LogService.log_warning("⚠️ Используется устаревший парсер для главы", chapter_id=chapter_number)
            return self._parse_chapter_with_legacy_system(chapter_url, chapter_number, novel)

    def _parse_chapter_with_new_system(self, chapter_url: str, chapter_number: int, novel: Novel = None) -> Optional[str]:
        """Парсинг содержимого главы с новой системой"""
        try:
            # Получаем cookies и прокси из настроек новеллы
            auth_cookies = None
            socks_proxy = None
            
            if novel:
                # Определяем, является ли глава VIP/платной
                is_vip_chapter = self._is_vip_chapter(chapter_number, chapter_url, novel)
                
                # Получаем подходящие cookies для типа контента
                if novel.is_auth_enabled() or novel.is_vip_cookies_enabled():
                    auth_cookies = novel.get_effective_cookies(is_vip_content=is_vip_chapter)
                    cookie_type = "VIP" if is_vip_chapter and novel.is_vip_cookies_enabled() else "обычные"
                    LogService.log_info(f"🔐 Используем {cookie_type} cookies для главы {chapter_number} (VIP: {is_vip_chapter})", chapter_id=chapter_number)
                
                if novel.is_proxy_enabled():
                    socks_proxy = novel.get_socks_proxy()
                    LogService.log_info(f"🌐 Используем SOCKS прокси для главы {chapter_number}: {socks_proxy}", chapter_id=chapter_number)
            
            # Создаем парсер для URL главы с cookies и прокси
            if novel and novel.is_epub_source():
                # Для EPUB используем специальный парсер
                epub_path = novel.get_epub_file_path()
                # ВАЖНО: передаем start_chapter, чтобы парсер правильно индексировал главы
                start_chapter = novel.config.get('start_chapter', 1) if novel.config else 1
                LogService.log_info(f"📖 Создаем EPUB парсер для главы с start_chapter={start_chapter}", chapter_id=chapter_number)
                parser = create_parser('epub', epub_path=epub_path, start_chapter=start_chapter)
            else:
                # Для веб-источников используем URL
                parser = create_parser_from_url(chapter_url, auth_cookies=auth_cookies, socks_proxy=socks_proxy)
            
            if not parser:
                LogService.log_warning(f"⚠️ Не удалось создать парсер для главы {chapter_number}, используем legacy", chapter_id=chapter_number)
                return self._parse_chapter_with_legacy_system(chapter_url, chapter_number, novel)
            
            # Получаем содержимое главы
            chapter_data = parser.get_chapter_content(chapter_url)
            if not chapter_data or not chapter_data.get('content'):
                LogService.log_error(f"❌ Пустое содержимое главы {chapter_number}", chapter_id=chapter_number)
                parser.close()
                return None
            
            content = chapter_data['content']
            is_locked = chapter_data.get('is_locked', False)
            
            if is_locked:
                LogService.log_warning(f"🔒 Глава {chapter_number} заблокирована, получено превью: {len(content)} символов", chapter_id=chapter_number)
                # Для заблокированных глав возвращаем превью с пометкой
                if len(content) < 200:
                    content = f"[ЗАБЛОКИРОВАНА - ПРЕВЬЮ] {content}"
            else:
                LogService.log_info(f"✅ Глава {chapter_number} загружена: {len(content)} символов", chapter_id=chapter_number)
            
            # Закрываем парсер
            parser.close()
            
            return content
            
        except Exception as e:
            LogService.log_error(f"❌ Ошибка парсинга главы {chapter_number} новой системой: {e}", chapter_id=chapter_number)
            # Откат к старой системе
            return self._parse_chapter_with_legacy_system(chapter_url, chapter_number, novel)

    def _is_vip_chapter(self, chapter_number: int, chapter_url: str, novel) -> bool:
        """Определение VIP/платных глав"""
        try:
            # Для Qidian главы после 130 обычно VIP
            if 'qidian.com' in chapter_url:
                if chapter_number and int(chapter_number) > 130:
                    return True
            
            # Проверяем URL на наличие VIP индикаторов
            if 'vip' in chapter_url.lower():
                return True
            
            # Можно добавить другие проверки для других сайтов
            
            return False
            
        except Exception as e:
            LogService.log_warning(f"⚠️ Ошибка при определении VIP статуса главы {chapter_number}: {e}")
            return False
    
    def _parse_chapter_with_legacy_system(self, chapter_url: str, chapter_number: int, novel: Novel = None) -> Optional[str]:
        """Устаревший парсер для содержимого глав"""

        try:
            # Специальная обработка для EPUB источников
            if novel and novel.is_epub_source():
                LogService.log_info(f"📖 Обработка EPUB главы {chapter_number} в legacy системе", chapter_id=chapter_number)
                try:
                    from parsers.sources.epub_parser import EPUBParser
                    epub_path = novel.get_epub_file_path()
                    
                    if not epub_path or not os.path.exists(epub_path):
                        LogService.log_error(f"EPUB файл не найден: {epub_path}", chapter_id=chapter_number)
                        return None
                    
                    # Получаем начальную главу из конфига новеллы
                    start_chapter = novel.config.get('start_chapter', 1) if novel and novel.config else 1
                    
                    # При загрузке контента главы тоже нужно учитывать start_chapter
                    LogService.log_info(f"📖 [Legacy content] Создаем EPUB парсер для главы {chapter_number}: start_chapter={start_chapter}", chapter_id=chapter_number)
                    parser = EPUBParser(epub_path=epub_path, start_chapter=start_chapter)
                    if not parser.load_epub(epub_path):
                        LogService.log_error("Не удалось загрузить EPUB файл", chapter_id=chapter_number)
                        return None
                    
                    # Получаем содержимое главы
                    chapter_data = parser.get_chapter_content(chapter_url)
                    parser.close()
                    
                    if chapter_data and chapter_data.get('content'):
                        LogService.log_info(f"✅ EPUB глава {chapter_number} загружена: {len(chapter_data['content'])} символов", chapter_id=chapter_number)
                        return chapter_data['content']
                    else:
                        LogService.log_error(f"❌ Пустое содержимое EPUB главы {chapter_number}", chapter_id=chapter_number)
                        return None
                        
                except Exception as e:
                    LogService.log_error(f"Ошибка обработки EPUB главы {chapter_number} в legacy системе: {e}", chapter_id=chapter_number)
                    return None
            
            # Для веб-источников загружаем страницу главы
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

                # РАСШИРЕННАЯ ПРОВЕРКА НА СУЩЕСТВОВАНИЕ ГЛАВЫ
                # Проверяем по номеру главы И по URL для большей надежности
                existing_chapter = Chapter.query.filter(
                    Chapter.novel_id == novel_id,
                    db.or_(
                        Chapter.chapter_number == chapter_data['number'],
                        Chapter.url == chapter_data['url']
                    )
                ).first()
                
                if existing_chapter:
                    LogService.log_info(f"Глава {chapter_data['number']} уже существует (ID: {existing_chapter.id}, статус: {existing_chapter.status})", 
                                      novel_id=novel_id, task_id=task_id)
                    
                    # Проверяем статус существующей главы
                    if existing_chapter.status in ['parsed', 'translated', 'edited']:
                        LogService.log_info(f"Пропускаем главу {chapter_data['number']} - уже обработана", 
                                          novel_id=novel_id, task_id=task_id)
                        continue
                    else:
                        # Если глава в статусе 'pending' или 'error', обновляем её
                        LogService.log_info(f"Обновляем существующую главу {chapter_data['number']} (статус: {existing_chapter.status})", 
                                          novel_id=novel_id, task_id=task_id)
                        update_existing = True
                        chapter_to_update = existing_chapter
                else:
                    update_existing = False
                    chapter_to_update = None

                # Парсим содержимое
                LogService.log_info(f"Загрузка содержимого главы {chapter_data['number']}...", 
                                  novel_id=novel_id, task_id=task_id)
                content = self.parse_chapter_content(chapter_data['url'], chapter_data['number'], novel)
                if not content:
                    LogService.log_warning(f"Не удалось загрузить содержимое главы {chapter_data['number']}", 
                                         novel_id=novel_id, task_id=task_id)
                    continue

                # Создаем или обновляем главу в БД
                if update_existing:
                    # Обновляем существующую главу
                    chapter_to_update.original_title = chapter_data['title']
                    chapter_to_update.url = chapter_data['url']
                    chapter_to_update.original_text = content
                    chapter_to_update.word_count_original = len(content) if content else 0
                    chapter_to_update.status = 'parsed'
                    
                    chapter = chapter_to_update
                    LogService.log_info(f"Глава {chapter_data['number']} обновлена в БД", 
                                      novel_id=novel_id, task_id=task_id, chapter_id=chapter.id)
                else:
                    # Создаем новую главу
                    LogService.log_info(f"🆕 Создаем новую главу в БД:", novel_id=novel_id, task_id=task_id)
                    LogService.log_info(f"   - Номер: {chapter_data['number']}", novel_id=novel_id, task_id=task_id)
                    LogService.log_info(f"   - Заголовок: {chapter_data['title']}", novel_id=novel_id, task_id=task_id)
                    LogService.log_info(f"   - URL: {chapter_data['url']}", novel_id=novel_id, task_id=task_id)
                    LogService.log_info(f"   - Размер контента: {len(content) if content else 0} символов", novel_id=novel_id, task_id=task_id)
                    LogService.log_info(f"   - Первые 100 символов: {content[:100] if content else 'пусто'}...", novel_id=novel_id, task_id=task_id)
                    
                    chapter = Chapter(
                        novel_id=novel_id,
                        chapter_number=chapter_data['number'],
                        original_title=chapter_data['title'],
                        url=chapter_data['url'],
                        original_text=content,
                        word_count_original=len(content) if content else 0,
                        status='parsed'
                    )
                    db.session.add(chapter)
                    LogService.log_info(f"Глава {chapter_data['number']} создана в БД", 
                                      novel_id=novel_id, task_id=task_id, chapter_id=chapter.id)
                
                success_count += 1
                
                # Принудительно коммитим каждую главу для избежания race conditions
                try:
                    db.session.commit()
                    LogService.log_info(f"Глава {chapter_data['number']} успешно сохранена", 
                                      novel_id=novel_id, task_id=task_id, chapter_id=chapter.id)
                except Exception as e:
                    db.session.rollback()
                    
                    # Проверяем, не является ли это ошибкой уникальности
                    if "UNIQUE constraint failed" in str(e):
                        LogService.log_warning(f"Глава {chapter_data['number']} уже существует (обнаружено при сохранении)", 
                                             novel_id=novel_id, task_id=task_id)
                        # Не считаем это ошибкой, просто пропускаем
                        success_count -= 1  # Убираем из счетчика успешных
                        continue
                    else:
                        LogService.log_error(f"Ошибка сохранения главы {chapter_data['number']}: {e}", 
                                           novel_id=novel_id, task_id=task_id)
                        success_count -= 1  # Убираем из счетчика успешных
                        continue

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