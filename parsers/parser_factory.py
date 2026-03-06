#!/usr/bin/env python3
"""
Фабрика парсеров для различных источников книг
Обеспечивает единый интерфейс для создания парсеров разных типов
"""
from typing import Dict, Optional, Type
from urllib.parse import urlparse
import re

from .base.base_parser import BaseParser
from .sources.qidian_parser import QidianParser
from .sources.epub_parser import EPUBParser
from .sources.czbooks_parser import CZBooksParser
from .sources.ttkan_parser import TtkanParser


class ParserFactory:
    """
    Фабрика для создания парсеров на основе URL или типа источника
    """
    
    # Реестр доступных парсеров
    _parsers: Dict[str, Type[BaseParser]] = {
        'qidian': QidianParser,
        'epub': EPUBParser,
        'czbooks': CZBooksParser,
        'ttkan': TtkanParser,
    }
    
    # Паттерны URL для автоматического определения парсера
    _url_patterns: Dict[str, str] = {
        r'qidian\.com': 'qidian',
        r'm\.qidian\.com': 'qidian',
        r'book\.qidian\.com': 'qidian',
        r'czbooks\.net': 'czbooks',
        r'ttkan\.co': 'ttkan',
        r'\.epub(?:/.*)?$': 'epub',  # Файлы EPUB (включая пути с дополнительными слешами)
        r'epub_files': 'epub',  # Директория с EPUB файлами
    }
    
    @classmethod
    def create_parser(cls, source: str, auth_cookies: str = None, socks_proxy: str = None, epub_path: str = None, max_chapters: int = None, start_chapter: int = None, headless: bool = True, cloudflare_max_attempts: int = 5) -> BaseParser:
        """
        Создать парсер по названию источника
        
        Args:
            source: Название источника ('qidian', 'webnovel', 'epub', etc.)
            auth_cookies: Cookies для авторизации (опционально)
            socks_proxy: SOCKS прокси для обхода блокировок (опционально)
            epub_path: Путь к EPUB файлу (только для source='epub')
            max_chapters: Максимальное количество глав (опционально)
            start_chapter: Номер главы, с которой начать парсинг (только для EPUB)
            
        Returns:
            Экземпляр парсера для указанного источника
            
        Raises:
            ValueError: Если парсер для источника не найден
        """
        source = source.lower()
        
        if source not in cls._parsers:
            available = ", ".join(cls._parsers.keys())
            raise ValueError(f"Парсер для '{source}' не найден. Доступные: {available}")
        
        parser_class = cls._parsers[source]
        
        # Специальная обработка для EPUB парсера
        if source == 'epub':
            if not epub_path:
                raise ValueError("Для EPUB парсера необходимо указать путь к файлу (epub_path)")
            return parser_class(epub_path=epub_path, max_chapters=max_chapters, start_chapter=start_chapter)
        
        # Проверяем поддерживает ли парсер SOCKS прокси и headless
        try:
            return parser_class(auth_cookies=auth_cookies, socks_proxy=socks_proxy, headless=headless, cloudflare_max_attempts=cloudflare_max_attempts)
        except TypeError:
            # Fallback для парсеров без поддержки cloudflare_max_attempts
            try:
                return parser_class(auth_cookies=auth_cookies, socks_proxy=socks_proxy, headless=headless)
            except TypeError:
                # Fallback для парсеров без поддержки headless
                try:
                    return parser_class(auth_cookies=auth_cookies, socks_proxy=socks_proxy)
                except TypeError:
                    # Fallback для парсеров без поддержки прокси
                    return parser_class(auth_cookies=auth_cookies)
    
    @classmethod
    def create_parser_from_url(cls, url: str, auth_cookies: str = None, socks_proxy: str = None, headless: bool = False, cloudflare_max_attempts: int = 5) -> BaseParser:
        """
        Создать парсер на основе URL

        Args:
            url: URL книги или сайта
            auth_cookies: Cookies для авторизации (опционально)
            socks_proxy: SOCKS прокси для обхода блокировок (опционально)
            cloudflare_max_attempts: Количество попыток прохождения Cloudflare (только для czbooks)

        Returns:
            Экземпляр подходящего парсера

        Raises:
            ValueError: Если не удается определить тип парсера по URL
        """
        source = cls.detect_source_from_url(url)

        if not source:
            raise ValueError(f"Не удается определить источник по URL: {url}")

        return cls.create_parser(source, auth_cookies=auth_cookies, socks_proxy=socks_proxy, headless=headless, cloudflare_max_attempts=cloudflare_max_attempts)
    
    @classmethod
    def detect_source_from_url(cls, url: str) -> Optional[str]:
        """
        Определить тип источника по URL
        
        Args:
            url: URL для анализа
            
        Returns:
            Название источника или None, если не удается определить
        """
        for pattern, source in cls._url_patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                return source
        
        return None
    
    @classmethod
    def get_available_sources(cls) -> list:
        """
        Получить список доступных источников
        
        Returns:
            Список названий доступных источников
        """
        return list(cls._parsers.keys())
    
    @classmethod
    def register_parser(cls, source: str, parser_class: Type[BaseParser], url_patterns: Optional[list] = None):
        """
        Зарегистрировать новый парсер
        
        Args:
            source: Название источника
            parser_class: Класс парсера (должен наследоваться от BaseParser)
            url_patterns: Список регулярных выражений для автоопределения по URL
        """
        if not issubclass(parser_class, BaseParser):
            raise ValueError("Класс парсера должен наследоваться от BaseParser")
        
        cls._parsers[source.lower()] = parser_class
        
        # Добавляем паттерны URL если они предоставлены
        if url_patterns:
            for pattern in url_patterns:
                cls._url_patterns[pattern] = source.lower()
    
    @classmethod
    def get_parser_info(cls, source: str) -> Dict:
        """
        Получить информацию о парсере
        
        Args:
            source: Название источника
            
        Returns:
            Словарь с информацией о парсере
        """
        source = source.lower()
        
        if source not in cls._parsers:
            raise ValueError(f"Парсер для '{source}' не найден")
        
        parser_class = cls._parsers[source]
        
        # Собираем паттерны URL для этого источника
        url_patterns = [pattern for pattern, src in cls._url_patterns.items() if src == source]
        
        return {
            'source': source,
            'class': parser_class.__name__,
            'module': parser_class.__module__,
            'url_patterns': url_patterns,
            'description': parser_class.__doc__ or "Нет описания"
        }
    
    @classmethod
    def list_all_parsers(cls) -> Dict:
        """
        Получить информацию обо всех зарегистрированных парсерах
        
        Returns:
            Словарь с информацией о всех парсерах
        """
        return {source: cls.get_parser_info(source) for source in cls._parsers.keys()}


# Удобные функции для быстрого использования
def create_parser(source: str, auth_cookies: str = None, socks_proxy: str = None, epub_path: str = None, max_chapters: int = None, start_chapter: int = None) -> BaseParser:
    """Создать парсер по названию источника"""
    return ParserFactory.create_parser(source, auth_cookies=auth_cookies, socks_proxy=socks_proxy, epub_path=epub_path, max_chapters=max_chapters, start_chapter=start_chapter)


def create_parser_from_url(url: str, auth_cookies: str = None, socks_proxy: str = None, headless: bool = False, cloudflare_max_attempts: int = 5) -> BaseParser:
    """Создать парсер на основе URL"""
    return ParserFactory.create_parser_from_url(url, auth_cookies=auth_cookies, socks_proxy=socks_proxy, headless=headless, cloudflare_max_attempts=cloudflare_max_attempts)


def detect_source(url: str) -> Optional[str]:
    """
    Определить тип источника по URL
    """
    return ParserFactory.detect_source_from_url(url)


def get_available_sources() -> list:
    """
    Получить список доступных источников
    """
    return ParserFactory.get_available_sources()


def main():
    """
    Демонстрация работы фабрики парсеров
    """
    print("🏭 PARSER FACTORY - Демонстрация")
    print("=" * 50)
    
    # Показываем доступные парсеры
    print("📋 Доступные парсеры:")
    parsers_info = ParserFactory.list_all_parsers()
    for source, info in parsers_info.items():
        print(f"  📚 {source.upper()}")
        print(f"     Класс: {info['class']}")
        print(f"     URL паттерны: {info['url_patterns']}")
        print()
    
    # Тестируем автоопределение источника
    test_urls = [
        "https://www.qidian.com/book/1209977/",
        "https://m.qidian.com/book/1209977/",
        "https://example.com/book/123"
    ]
    
    print("🔍 Тестирование автоопределения источника:")
    for url in test_urls:
        source = detect_source(url)
        if source:
            print(f"  ✅ {url} -> {source}")
        else:
            print(f"  ❌ {url} -> не распознан")
    print()
    
    # Создаем парсер и тестируем
    try:
        print("🚀 Создание парсера Qidian...")
        parser = create_parser('qidian')
        stats = parser.get_stats()
        print(f"  ✅ Парсер создан: {parser.source_name}")
        print(f"  📊 Начальная статистика: {stats}")
        parser.close()
        
    except Exception as e:
        print(f"  ❌ Ошибка создания парсера: {e}")


if __name__ == "__main__":
    main()