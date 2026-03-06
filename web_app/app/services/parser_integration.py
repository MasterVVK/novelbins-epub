#!/usr/bin/env python3
"""
Интеграция новой системы парсеров в веб-приложение
Мостик между веб-интерфейсом и системой парсеров
"""
import sys
import os
from typing import Dict, List, Optional

# Добавляем корневую директорию проекта в путь
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

try:
    from parsers import get_available_sources, create_parser, create_parser_from_url, detect_source
    PARSERS_AVAILABLE = True
except ImportError as e:
    print(f"Предупреждение: Система парсеров недоступна: {e}")
    print("Используется fallback режим с базовой функциональностью")
    PARSERS_AVAILABLE = False
    
    # Fallback - базовые функции для совместимости
    def get_available_sources():
        return ['novelbins']
    
    def create_parser(source):
        return None
    
    def create_parser_from_url(url):
        return None
    
    def detect_source(url):
        if 'qidian.com' in url.lower():
            return 'qidian'
        return 'novelbins'


class ParserIntegrationService:
    """
    Сервис для интеграции системы парсеров в веб-приложение
    """
    
    # Описания источников для пользователей
    SOURCE_DESCRIPTIONS = {
        'qidian': {
            'name': 'Qidian (起点中文网)',
            'description': 'Китайская платформа веб-новелл',
            'supported_languages': ['zh'],
            'example_url': 'https://www.qidian.com/book/1209977/',
            'features': ['Автоопределение', 'Обход защиты', 'Мобильная версия']
        },
        'novelbins': {
            'name': 'NovelBins',
            'description': 'Английская платформа переводов',
            'supported_languages': ['en'],
            'example_url': 'https://novelbins.net/novel/...',
            'features': ['Стандартный парсер']
        },
        'ttkan': {
            'name': 'TTKan (天天看小說)',
            'description': 'Китайская платформа веб-новелл (традиционные иероглифы)',
            'supported_languages': ['zh'],
            'example_url': 'https://ttkan.co/novel/chapters/xuezhonghandaoxing-fenghuoxizhuhou',
            'features': ['Автоопределение', 'HTTP парсер']
        },
        'epub': {
            'name': 'EPUB файл',
            'description': 'Локальный EPUB файл для импорта',
            'supported_languages': ['en', 'zh', 'ru', 'auto'],
            'example_url': 'book.epub',
            'features': ['Локальный файл', 'Автоопределение языка', 'Извлечение глав']
        }
    }
    
    @classmethod
    def get_available_sources_with_info(cls) -> List[Dict]:
        """
        Получить список доступных источников с подробной информацией
        
        Returns:
            List[Dict]: Список источников с описаниями
        """
        available = get_available_sources()
        sources_info = []
        
        for source in available:
            info = cls.SOURCE_DESCRIPTIONS.get(source, {
                'name': source.capitalize(),
                'description': f'Парсер для {source}',
                'supported_languages': ['unknown'],
                'example_url': '',
                'features': ['Базовая поддержка'] if not PARSERS_AVAILABLE else []
            })
            
            # Добавляем информацию о режиме работы
            if not PARSERS_AVAILABLE and source == 'novelbins':
                info['features'].append('Fallback режим')
            
            sources_info.append({
                'id': source,
                'name': info['name'],
                'description': info['description'],
                'supported_languages': info['supported_languages'],
                'example_url': info['example_url'],
                'features': info['features']
            })
        
        return sources_info
    
    @classmethod
    def detect_source_from_url(cls, url: str) -> Optional[str]:
        """
        Определить источник по URL
        
        Args:
            url: URL для анализа
            
        Returns:
            Название источника или None
        """
        try:
            return detect_source(url)
        except Exception as e:
            print(f"Ошибка определения источника: {e}")
            return None
    
    @classmethod
    def create_parser_for_url(cls, url: str):
        """
        Создать парсер для URL
        
        Args:
            url: URL книги
            
        Returns:
            Экземпляр парсера или None при ошибке
        """
        try:
            return create_parser_from_url(url)
        except Exception as e:
            print(f"Ошибка создания парсера: {e}")
            return None
    
    @classmethod
    def create_parser_by_type(cls, source_type: str):
        """
        Создать парсер по типу источника
        
        Args:
            source_type: Тип источника
            
        Returns:
            Экземпляр парсера или None при ошибке
        """
        try:
            return create_parser(source_type)
        except Exception as e:
            print(f"Ошибка создания парсера {source_type}: {e}")
            return None
    
    @classmethod
    def validate_url_for_source(cls, url: str, expected_source: str) -> bool:
        """
        Проверить, соответствует ли URL ожидаемому источнику
        
        Args:
            url: URL для проверки
            expected_source: Ожидаемый источник
            
        Returns:
            True если URL соответствует источнику
        """
        # Специальная обработка для EPUB источников
        if expected_source == 'epub':
            # For EPUB, check if it's a file path ending with .epub or contains epub_files directory
            return (url.lower().endswith('.epub') or 
                   'epub_files' in url or 
                   url.lower().endswith('.epub/'))
        
        detected = cls.detect_source_from_url(url)
        return detected == expected_source
    
    @classmethod
    def get_parser_info(cls, source: str) -> Dict:
        """
        Получить информацию о парсере
        
        Args:
            source: Название источника
            
        Returns:
            Словарь с информацией о парсере
        """
        return cls.SOURCE_DESCRIPTIONS.get(source, {
            'name': source.capitalize(),
            'description': f'Парсер для {source}',
            'supported_languages': ['unknown'],
            'example_url': '',
            'features': []
        })


def test_integration():
    """
    Тестирование интеграции парсеров
    """
    print("🧪 ТЕСТИРОВАНИЕ ИНТЕГРАЦИИ ПАРСЕРОВ")
    print("=" * 50)
    
    # Получаем доступные источники
    sources = ParserIntegrationService.get_available_sources_with_info()
    print(f"📋 Доступные источники ({len(sources)}):")
    for source in sources:
        print(f"  📚 {source['id']}: {source['name']}")
        print(f"     {source['description']}")
        print(f"     Языки: {', '.join(source['supported_languages'])}")
        print(f"     Функции: {', '.join(source['features'])}")
        print()
    
    # Тестируем автоопределение
    test_urls = [
        "https://www.qidian.com/book/1209977/",
        "https://m.qidian.com/book/1209977/",
        "https://novelbins.net/novel/test"
    ]
    
    print("🔍 Тестирование автоопределения:")
    for url in test_urls:
        detected = ParserIntegrationService.detect_source_from_url(url)
        print(f"  {url} -> {detected or 'не распознан'}")
    
    print("\n✅ Интеграция готова к использованию!")


if __name__ == "__main__":
    test_integration()