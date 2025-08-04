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
import base64
import json
import zlib

# Импорт Selenium для расшифровки (опционально)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    selenium_available = True
except ImportError:
    selenium_available = False

# Добавляем путь к базовому классу
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'base'))
from base_parser import BaseParser


class QidianParser(BaseParser):
    """
    Парсер для Qidian.com (китайская платформа веб-новелл)
    Использует мобильную версию для обхода защиты от ботов
    """
    
    def __init__(self, auth_cookies: str = None, socks_proxy: str = None):
        super().__init__("qidian")
        
        # Пул User-Agent'ов для ротации
        self.user_agents = [
            'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
            'Mozilla/5.0 (Linux; Android 10; Mi 9T Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
            'Mozilla/5.0 (iPad; CPU OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1'
        ]
        self.current_ua_index = 0
        
        # Cookies для авторизации
        self.auth_cookies = auth_cookies
        
        # SOCKS прокси для обхода WAF
        self.socks_proxy = socks_proxy
        if socks_proxy:
            print(f"🌐 Используем SOCKS прокси: {socks_proxy}")
            self._setup_proxy_session()
        
        # Устанавливаем начальные заголовки
        self._update_headers()
        
        # Базовые URL
        self.mobile_base_url = "https://m.qidian.com"
        
        # Счетчики для адаптивных пауз
        self.consecutive_errors = 0
    
    def _setup_proxy_session(self):
        """Настройка сессии с SOCKS прокси"""
        try:
            import requests
            from requests.adapters import HTTPAdapter
            import urllib3
            
            # Проверяем формат прокси
            if ':' in self.socks_proxy:
                proxy_host, proxy_port = self.socks_proxy.split(':', 1)
                proxy_url = f'socks5://{proxy_host}:{proxy_port}'
                
                # Создаем новую сессию с прокси
                proxies = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                
                self.session.proxies.update(proxies)
                print(f"✅ SOCKS прокси настроен: {proxy_url}")
            else:
                print(f"❌ Неверный формат прокси: {self.socks_proxy}")
                
        except ImportError as e:
            print(f"❌ Для SOCKS прокси требуется requests[socks]: {e}")
        except Exception as e:
            print(f"❌ Ошибка настройки прокси: {e}")
        
    def _update_headers(self):
        """Обновляем заголовки с новым User-Agent и cookies"""
        headers = {
            'User-Agent': self.user_agents[self.current_ua_index],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        # Добавляем cookies если есть
        if self.auth_cookies:
            headers['Cookie'] = self.auth_cookies
            print(f"🔐 Используем авторизацию: {len(self.auth_cookies)} символов cookies")
        
        self.session.headers.update(headers)
        
    def _rotate_user_agent(self):
        """Переключаем на следующий User-Agent"""
        self.current_ua_index = (self.current_ua_index + 1) % len(self.user_agents)
        self._update_headers()
        print(f"🔄 Переключение User-Agent: {self.user_agents[self.current_ua_index][:50]}...")
    
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
        Получить содержимое главы с поддержкой расшифровки
        """
        html_content = self._get_page_content(chapter_url, description="Содержимое главы")
        
        if not html_content:
            raise Exception(f"Не удалось получить содержимое главы: {chapter_url}")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Извлекаем заголовок главы
            title_selectors = [
                'h2.title',
                '.title',
                'h1.chapter__title',
                'h1',
                'h2'
            ]
            
            title = "Неизвестная глава"
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and len(title) > 5:
                        break
            
            # Извлекаем chapter_id
            chapter_id = self._extract_chapter_id(chapter_url)
            
            # Находим содержимое главы для анализа блокировки
            content_selectors = [
                'main[data-type="cjk"]',
                'main.content',
                '#reader-content main',
                'main',
                '.content'
            ]
            
            content_elem = None
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    break
                    
            if not content_elem:
                raise Exception("Не удалось найти содержимое главы")
            
            # Проверяем на блокировку
            is_locked = "lock-mask" in str(content_elem)
            
            # Если глава заблокирована, СНАЧАЛА пробуем расшифровку
            if is_locked:
                print(f"   🔒 Глава заблокирована (lock-mask) - пробуем расшифровку...")
                
                # Ищем зашифрованный контент в JSON
                encrypted_content = self._extract_encrypted_content(html_content)
                
                if encrypted_content:
                    print(f"   🔐 Найден зашифрованный контент: {len(encrypted_content)} символов")
                    
                    # Сначала пробуем простые алгоритмы
                    decrypted_text = self._decrypt_qidian_content(encrypted_content)
                    
                    if decrypted_text and len(decrypted_text) > 500:
                        print(f"   ✅ Контент расшифрован простым алгоритмом: {len(decrypted_text)} символов")
                        return {
                            'title': title,
                            'content': decrypted_text,
                            'chapter_id': chapter_id,
                            'word_count': len(decrypted_text),
                            'is_locked': False,
                            'is_decrypted': True
                        }
                    else:
                        print(f"   ⚠️ Простая расшифровка не удалась, пробуем Selenium...")
                        
                        # Fallback: используем Selenium для JavaScript расшифровки
                        if selenium_available and self.auth_cookies:
                            selenium_result = self._decrypt_with_selenium(chapter_url)
                            if selenium_result and len(selenium_result) > 500:
                                print(f"   ✅ Контент расшифрован через Selenium: {len(selenium_result)} символов")
                                return {
                                    'title': title,
                                    'content': selenium_result,
                                    'chapter_id': chapter_id,
                                    'word_count': len(selenium_result),
                                    'is_locked': False,
                                    'is_decrypted': True
                                }
                        
                        print(f"   ❌ Расшифровка не удалась - возвращаем заблокированный контент")
                else:
                    print(f"   ❌ Зашифрованный контент не найден")
            else:
                # Если глава не заблокирована, всё равно проверяем на зашифрованный контент
                encrypted_content = self._extract_encrypted_content(html_content)
                if encrypted_content:
                    print(f"   🔐 Найден зашифрованный контент (незаблокированная глава): {len(encrypted_content)} символов")
                    
                    # Пробуем простые алгоритмы
                    decrypted_text = self._decrypt_qidian_content(encrypted_content)
                    if decrypted_text and len(decrypted_text) > 500:
                        print(f"   ✅ Контент расшифрован простым алгоритмом: {len(decrypted_text)} символов")
                        return {
                            'title': title,
                            'content': decrypted_text,
                            'chapter_id': chapter_id,
                            'word_count': len(decrypted_text),
                            'is_locked': False,
                            'is_decrypted': True
                        }
                    else:
                        print(f"   ⚠️ Простая расшифровка не удалась, пробуем Selenium...")
                        
                        # Fallback: используем Selenium для JavaScript расшифровки
                        if selenium_available and self.auth_cookies:
                            selenium_result = self._decrypt_with_selenium(chapter_url)
                            if selenium_result and len(selenium_result) > 500:
                                # Очищаем Selenium результат от лишнего
                                cleaned_result = self._clean_selenium_result(selenium_result)
                                print(f"   ✅ Контент расшифрован через Selenium: {len(cleaned_result)} символов")
                                return {
                                    'title': title,
                                    'content': cleaned_result,
                                    'chapter_id': chapter_id,
                                    'word_count': len(cleaned_result),
                                    'is_locked': False,
                                    'is_decrypted': True
                                }
                        
                        print(f"   ❌ Selenium расшифровка не удалась")
            
            # Обычный парсинг HTML контента (если расшифровка не удалась или не нужна)
            content = self._clean_chapter_content(content_elem)
            
            # Если глава заблокирована и контента мало, помечаем как заблокированную
            if is_locked and len(content) < 200:
                print(f"   🔒 Глава заблокирована, получено превью: {len(content)} символов")
                content = f"[ЗАБЛОКИРОВАНА] {content}"
            
            return {
                'title': title,
                'content': content,
                'chapter_id': chapter_id,
                'word_count': len(content),
                'is_locked': is_locked,
                'is_decrypted': False
            }
        except Exception as e:
            print(f"⚠️ Ошибка парсинга содержимого главы: {e}")
            return {
                'title': 'Недоступная глава',
                'content': 'Содержимое главы недоступно из-за ограничений сайта.',
                'chapter_id': self._extract_chapter_id(chapter_url) or '0',
                'word_count': 0,
                'is_locked': True,
                'is_decrypted': False
            }
    
    def _delay_between_requests(self):
        """
        Адаптивная пауза между запросами для Qidian
        """
        # Базовая пауза
        base_delay = 2.0  # Увеличили базовую паузу
        
        # Увеличиваем паузу при ошибках
        if self.consecutive_errors > 0:
            # Больше увеличиваем паузу при ошибках
            base_delay *= (1 + self.consecutive_errors * 1.0)  # Увеличили множитель
        
        # Максимальная пауза 60 секунд
        base_delay = min(base_delay, 60.0)
        
        # Случайная составляющая для имитации человека
        random_factor = random.uniform(0.5, 1.5)  # Увеличили случайность
        delay = base_delay + random_factor
        
        print(f"⏳ Пауза {delay:.1f}s (ошибок подряд: {self.consecutive_errors})...")
        time.sleep(delay)
    
    def _get_page_content(self, url: str, timeout: int = 10, description: str = "") -> Optional[str]:
        """
        Переопределяем метод для специфичной обработки Qidian
        """
        try:
            self.request_count += 1
            
            if description:
                print(f"🌐 {description}: {url}")
            else:
                print(f"🌐 Запрос: {url}")
            
            response = self.session.get(url, timeout=timeout)
            
            print(f"   Статус: {response.status_code}")
            print(f"   Размер: {len(response.content):,} байт")
            
            if response.status_code == 200:
                html_content = response.text
                
                # Проверяем качество HTML для Qidian
                # Проверяем качество HTML
                is_valid_html = (
                    html_content and 
                    len(html_content) > 1000 and  # Уменьшили минимальный размер
                    html_content.strip().startswith('<')
                )
                
                # Проверяем на Qidian маркеры
                has_qidian_markers = (
                    '起点中文网' in html_content or 
                    'qidian.com' in html_content or
                    'reader-content' in html_content or
                    'chapter' in html_content.lower()
                )
                
                if is_valid_html and has_qidian_markers:
                    self.success_count += 1
                    self.consecutive_errors = 0
                    print(f"✅ Качественный HTML получен ({len(html_content)} символов)")
                    return html_content
                else:
                    print("⚠️ HTML не прошел проверку качества")
                    print(f"   Размер: {len(html_content)}, HTML: {is_valid_html}, Qidian: {has_qidian_markers}")
                    self.consecutive_errors += 1
                    
            elif response.status_code == 202:
                print("⚠️ Сервер возвращает 202 - возможная защита от ботов")
                self.consecutive_errors += 1
                time.sleep(5)
                
            elif response.status_code == 403:
                print("⚠️ HTTP 403 Forbidden - защита от ботов")
                self.consecutive_errors += 1
                
                # Переключаем User-Agent при ошибках 403
                self._rotate_user_agent()
                
                # Увеличиваем задержку при 403 ошибке
                delay = 15 + (self.consecutive_errors * 5)  # Минимум 15 сек, +5 сек за каждую ошибку
                print(f"⏳ Увеличенная пауза: {delay} секунд...")
                time.sleep(delay)
                
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
        Очистить содержимое главы от лишних элементов (исправленная версия)
        """
        # Удаляем ненужные элементы (расширенный список)
        unwanted_selectors = [
            'script', 'style', '.ad', '.advertisement', '.nav', '.navigation',
            '.header', '.footer', '.sidebar', '.comment', '.share', '.social',
            '.related', '.recommend', '[class*="ad"]', '[class*="banner"]',
            '.download-bar', '.icon-container', '.y-button', '.auto-tr'
        ]
        
        for selector in unwanted_selectors:
            for unwanted in content_elem.select(selector):
                unwanted.decompose()
        
        # Получаем текст с сохранением структуры
        paragraphs = []
        
        # Сначала пробуем найти правильные параграфы
        for p in content_elem.find_all('p'):
            text = p.get_text(strip=True)
            if text and len(text) > 10:  # Уменьшили минимальную длину
                # Убираем лишние пробелы в начале
                text = text.lstrip('　')  # Убираем китайские пробелы
                if text and len(text) > 10:
                    paragraphs.append(text)
        
        # Если не нашли параграфы, ищем в div'ах
        if not paragraphs:
            for div in content_elem.find_all('div'):
                text = div.get_text(strip=True)
                if text and len(text) > 20:
                    # Проверяем, что это не навигация
                    if not any(nav_word in text.lower() for nav_word in ['目录', '下一章', '上一章', 'menu', 'next', 'prev', 'app', '下载']):
                        paragraphs.append(text)
        
        # Если все еще пусто, берем весь текст
        if not paragraphs:
            full_text = content_elem.get_text(strip=True)
            if full_text:
                # Разбиваем по строкам и фильтруем
                lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                paragraphs = [line for line in lines if len(line) > 10]
        
        result = '\n\n'.join(paragraphs) if paragraphs else "Нет содержимого"
        
        # Отладочная информация
        if len(result) > 50:  # Показываем отладку только для непустого контента
            print(f"   📝 Очищено содержимое: {len(paragraphs)} абзацев, {len(result)} символов")
        
        return result
    
    def _extract_encrypted_content(self, html_content: str) -> str:
        """
        Извлекаем зашифрованный контент из JSON данных страницы
        """
        try:
            # Ищем специфичные для Qidian JSON паттерны
            patterns = [
                # Основной паттерн - content поле с длинной строкой
                (r'"content"\s*:\s*"([^"]{1000,})"', "content field"),
                # Дополнительные паттерны
                (r'"chapterContent"\s*:\s*"([^"]{1000,})"', "chapterContent field"),
                (r'"text"\s*:\s*"([^"]{1000,})"', "text field"),
                (r'window\.__INITIAL_STATE__\s*=\s*({.+?});', "INITIAL_STATE"),
                (r'window\.g_data\s*=\s*({.+?});', "g_data")
            ]
            
            for pattern, name in patterns:
                matches = re.findall(pattern, html_content, re.DOTALL)
                for match in matches:
                    try:
                        if match.startswith('{'):
                            # JSON объект
                            data = json.loads(match)
                            content = self._find_encrypted_in_json(data)
                            if content:
                                print(f"   🎯 Зашифрованный контент найден в {name}")
                                return content
                        elif len(match) > 1000:
                            # Длинная строка - потенциально зашифрованный контент
                            if self._looks_like_base64(match):
                                print(f"   🎯 Зашифрованный контент найден в {name} (прямое совпадение)")
                                return match
                    except json.JSONDecodeError:
                        continue
            
            print(f"   ❌ Зашифрованный контент не найден в известных паттернах")
            return None
            
        except Exception as e:
            print(f"   ⚠️ Ошибка извлечения зашифрованного контента: {e}")
            return None
    
    def _find_encrypted_in_json(self, data, visited=None) -> str:
        """
        Рекурсивно ищем зашифрованные данные в JSON
        """
        if visited is None:
            visited = set()
        
        if id(data) in visited:
            return None
        visited.add(id(data))
        
        try:
            if isinstance(data, dict):
                # Поиск по ключам, которые могут содержать контент
                content_keys = ['content', 'chapterContent', 'text', 'body', 'data']
                for key in content_keys:
                    if key in data and isinstance(data[key], str) and len(data[key]) > 1000:
                        return data[key]
                
                # Рекурсивный поиск
                for value in data.values():
                    result = self._find_encrypted_in_json(value, visited)
                    if result:
                        return result
                        
            elif isinstance(data, list):
                for item in data:
                    result = self._find_encrypted_in_json(item, visited)
                    if result:
                        return result
            
            elif isinstance(data, str) and len(data) > 1000:
                # Проверяем, похоже ли контент на base64
                if self._looks_like_base64(data):
                    return data
            
            return None
            
        except Exception:
            return None
    
    def _looks_like_base64(self, text: str) -> bool:
        """
        Проверяем, похож ли текст на base64
        """
        # Простая проверка: только base64 символы и правильная длина
        base64_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
        return (
            len(text) > 100 and
            len(text) % 4 == 0 and  # Base64 всегда кратно 4
            all(c in base64_chars for c in text) and
            text.count('=') <= 2  # Максимум 2 знака padding
        )
    
    def _decrypt_qidian_content(self, encrypted_content: str) -> str:
        """
        Расшифровка контента Qidian с использованием известных алгоритмов
        """
        # Алгоритмы расшифровки в порядке приоритета
        decryption_methods = [
            ('zGup5_xor', self._decrypt_with_key, 'zGup5'),
            ('qidian_xor', self._decrypt_with_key, 'qidian'),
            ('reader_xor', self._decrypt_with_key, 'reader'),
            ('zGup5_zlib', self._decrypt_with_zlib, 'zGup5'),
            ('qidian_zlib', self._decrypt_with_zlib, 'qidian')
        ]
        
        for method_name, method_func, key in decryption_methods:
            try:
                result = method_func(encrypted_content, key)
                if result and self._is_valid_chinese_text(result):
                    print(f"   ✅ Расшифровка успешна методом: {method_name}")
                    return result
            except Exception as e:
                continue
        
        print(f"   ⚠️ Не удалось расшифровать контент")
        return None
    
    def _decrypt_with_key(self, encrypted_content: str, key: str) -> str:
        """
        Расшифровка с помощью XOR ключа
        """
        try:
            # Декодируем base64
            decoded = base64.b64decode(encrypted_content)
            
            # XOR дешифрование
            key_bytes = key.encode('utf-8')
            xored = bytes(decoded[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(decoded)))
            
            # Пробуем декодировать UTF-8
            return xored.decode('utf-8')
            
        except Exception:
            return None
    
    def _decrypt_with_zlib(self, encrypted_content: str, key: str) -> str:
        """
        Расшифровка с помощью XOR + zlib декомпрессии
        """
        try:
            # Декодируем base64
            decoded = base64.b64decode(encrypted_content)
            
            # XOR дешифрование
            key_bytes = key.encode('utf-8')
            xored = bytes(decoded[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(decoded)))
            
            # Декомпрессия zlib
            decompressed = zlib.decompress(xored)
            
            # Пробуем декодировать UTF-8
            return decompressed.decode('utf-8')
            
        except Exception:
            return None
    
    def _is_valid_chinese_text(self, text: str) -> bool:
        """
        Проверяем, является ли текст качественным китайским текстом
        """
        if not text or len(text) < 100:
            return False
        
        # Подсчитываем китайские символы
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        chinese_ratio = chinese_chars / len(text)
        
        # Проверяем ключевые слова (например, из названия главы)
        keywords_found = any(keyword in text for keyword in ['承诺', '完美', '我带', '孟昊'])
        
        # Критерии качества
        return (
            chinese_ratio > 0.15 or  # Минимум 15% китайских символов
            keywords_found or  # Найдены ключевые слова
            chinese_chars > 500  # Минимум 500 китайских символов
        )
    
    def _decrypt_with_selenium(self, chapter_url: str) -> str:
        """
        Расшифровка контента с помощью Selenium (JavaScript выполнение)
        """
        if not selenium_available:
            print(f"   ❌ Selenium не доступен")
            return None
        
        try:
            print(f"   🌐 Запуск Selenium для расшифровки...")
            
            # Настраиваем Chrome
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1')
            chrome_options.binary_location = "/usr/bin/chromium-browser"
            
            # Добавляем SOCKS прокси если настроен
            if self.socks_proxy:
                chrome_options.add_argument(f'--proxy-server=socks5://{self.socks_proxy}')
                chrome_options.add_argument('--host-resolver-rules="MAP * 0.0.0.0 , EXCLUDE localhost"')
                print(f"   🌐 Selenium использует SOCKS прокси: {self.socks_proxy}")
            
            service = Service('/usr/bin/chromedriver')
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Загружаем главную страницу для установки cookies
            driver.get("https://m.qidian.com/")
            time.sleep(2)
            
            # Устанавливаем cookies
            if self.auth_cookies:
                cookies_set = 0
                for cookie_pair in self.auth_cookies.split(';'):
                    if '=' in cookie_pair:
                        name, value = cookie_pair.strip().split('=', 1)
                        try:
                            driver.add_cookie({
                                'name': name.strip(),
                                'value': value.strip(),
                                'domain': '.qidian.com'
                            })
                            cookies_set += 1
                        except:
                            pass
                print(f"   🍪 Установлено cookies: {cookies_set}")
            
            # Загружаем страницу главы
            driver.get(chapter_url)
            
            # Постепенно увеличиваем время ожидания JavaScript
            wait_times = [5, 10, 15]
            for wait_time in wait_times:
                time.sleep(wait_time)
                print(f"   ⏳ Ожидание JavaScript выполнения: {wait_time} секунд...")
                
                # Извлекаем расшифрованный контент
                js_extractors = [
                    # Основной контейнер
                    "return document.querySelector('main') ? document.querySelector('main').innerText : '';",
                    # Все параграфы
                    "return Array.from(document.querySelectorAll('p')).map(p => p.innerText).join('\\n');",
                    # Весь body
                    "return document.body.innerText;",
                    # Китайские строки
                    "var allText = document.documentElement.innerText; var lines = allText.split('\\n'); var chineseLines = []; for (var i = 0; i < lines.length; i++) { var line = lines[i].trim(); if (line.length > 10) { var chineseCount = (line.match(/[\\u4e00-\\u9fff]/g) || []).length; if (chineseCount > 5) { chineseLines.push(line); } } } return chineseLines.join('\\n');",
                    # Поиск в элементах с классами содержимого
                    "var elements = document.querySelectorAll('div, section, article'); var texts = []; for (var i = 0; i < elements.length; i++) { var text = elements[i].innerText; if (text && text.length > 100) { var chineseCount = (text.match(/[\\u4e00-\\u9fff]/g) || []).length; if (chineseCount > 50) { texts.push(text); } } } return texts.join('\\n');"
                ]
                
                for i, js_code in enumerate(js_extractors):
                    try:
                        result = driver.execute_script(js_code)
                        if result and len(result.strip()) > 500:
                            chinese_chars = sum(1 for char in result if '\u4e00' <= char <= '\u9fff')
                            print(f"   📊 Метод {i+1} (ожидание {wait_time}s): {len(result)} символов, {chinese_chars} китайских")
                            
                            if chinese_chars > 200:  # Достаточно китайских символов
                                print(f"   ✅ Selenium извлечение успешно!")
                                driver.quit()
                                return result
                    except Exception as e:
                        continue
                
                # Если на этом этапе нашли что-то, но недостаточно качественное, запоминаем
                print(f"   ⏳ Продолжаем ожидание... (этап {wait_time}s завершен)")
            
            driver.quit()
            print(f"   ❌ Selenium не смог извлечь качественный контент")
            return None
            
        except Exception as e:
            print(f"   ❌ Ошибка Selenium: {e}")
            try:
                driver.quit()
            except:
                pass
            return None
    
    def _clean_selenium_result(self, selenium_text: str) -> str:
        """
        Очищаем результат Selenium от повторов и служебного текста
        """
        if not selenium_text:
            return ""
        
        # Разбиваем на строки
        lines = selenium_text.split('\n')
        
        # Убираем служебные строки (только самые очевидные)
        excluded_keywords = [
            '菜单', '章节加载失败', '不再显示订阅提醒', 'APP看广告免费解锁',
            '订阅本章', '批量订阅', '下一章'
        ]
        
        cleaned_lines = []
        seen_content = set()  # Для удаления дубликатов контента
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Пропускаем служебные строки
            is_service_line = False
            for keyword in excluded_keywords:
                if keyword in line:
                    is_service_line = True
                    break
            
            if is_service_line:
                continue
            
            # Проверяем на дубликаты только для длинных строк (основной контент)
            if len(line) > 20:
                if line in seen_content:
                    continue
                seen_content.add(line)
            
            # Добавляем строки с контентом (менее строгий фильтр)
            if len(line) > 3:
                cleaned_lines.append(line)
        
        # Объединяем в текст
        result = '\n\n'.join(cleaned_lines)
        
        # Мягкая очистка - убираем только повторяющиеся заголовки
        # Оставляем основной заголовок, убираем повторы
        title_pattern = r'第二卷 初入南域 第131章 我带承诺而来！'
        title_matches = re.findall(title_pattern, result)
        if len(title_matches) > 1:
            # Убираем все кроме первого вхождения
            result = re.sub(title_pattern, '', result)
            result = title_pattern + '\n\n' + result.strip()
        
        # Убираем строки с номерами точек и баланса
        result = re.sub(r'^\d+点$', '', result, flags=re.MULTILINE)
        result = re.sub(r'^余额\d+点$', '', result, flags=re.MULTILINE)
        
        # Очищаем лишние переносы
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result.strip()


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