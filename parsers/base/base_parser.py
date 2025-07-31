#!/usr/bin/env python3
"""
Базовый класс для всех парсеров книг
Предоставляет общий интерфейс и функциональность для парсинга различных источников
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import requests
import time
import json
import os
from urllib.parse import urljoin, urlparse


class BaseParser(ABC):
    """
    Абстрактный базовый класс для парсеров книг
    """
    
    def __init__(self, source_name: str):
        """
        Инициализация базового парсера
        
        Args:
            source_name: Название источника (например, "qidian", "webnovel")
        """
        self.source_name = source_name
        self.session = requests.Session()
        self.request_count = 0
        self.success_count = 0
        
        # Базовые заголовки (могут быть переопределены в дочерних классах)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    @abstractmethod
    def get_book_info(self, book_url: str) -> Dict:
        """
        Получить информацию о книге
        
        Args:
            book_url: URL книги
            
        Returns:
            Dict с информацией о книге:
            {
                'title': str,
                'author': str,
                'description': str,
                'status': str,
                'genre': str,
                'book_id': str,
                'total_chapters': int
            }
        """
        pass
    
    @abstractmethod
    def get_chapter_list(self, book_url: str) -> List[Dict]:
        """
        Получить список глав книги
        
        Args:
            book_url: URL книги
            
        Returns:
            List[Dict] со списком глав:
            [
                {
                    'number': int,
                    'title': str,
                    'url': str,
                    'chapter_id': str,
                    'word_count': int (optional)
                },
                ...
            ]
        """
        pass
    
    @abstractmethod
    def get_chapter_content(self, chapter_url: str) -> Dict:
        """
        Получить содержимое главы
        
        Args:
            chapter_url: URL главы
            
        Returns:
            Dict с содержимым главы:
            {
                'title': str,
                'content': str,
                'chapter_id': str,
                'word_count': int (optional)
            }
        """
        pass
    
    def download_book(self, book_url: str, output_dir: str, chapter_limit: Optional[int] = None) -> Dict:
        """
        Скачать всю книгу
        
        Args:
            book_url: URL книги
            output_dir: Директория для сохранения
            chapter_limit: Ограничение количества глав (None = все)
            
        Returns:
            Dict с результатами скачивания
        """
        print(f"📚 Начинаем скачивание книги: {book_url}")
        
        # Получаем информацию о книге
        book_info = self.get_book_info(book_url)
        print(f"📖 Книга: {book_info['title']} - {book_info['author']}")
        
        # Создаем директорию для книги
        book_dir = os.path.join(output_dir, book_info['title'])
        os.makedirs(book_dir, exist_ok=True)
        
        # Сохраняем информацию о книге
        book_info_path = os.path.join(book_dir, 'book_info.json')
        
        # Получаем список глав
        chapters = self.get_chapter_list(book_url)
        print(f"📑 Найдено глав: {len(chapters)}")
        
        # Применяем ограничение на количество глав
        if chapter_limit:
            chapters = chapters[:chapter_limit]
            print(f"📑 Ограничиваем до: {len(chapters)} глав")
        
        # Добавляем информацию о главах в book_info
        book_info['chapters'] = chapters[:3]  # Сохраняем первые 3 для примера
        book_info['total_chapters'] = len(chapters)
        book_info['parsed_chapters'] = 0
        
        downloaded_chapters = []
        failed_chapters = []
        
        # Скачиваем главы
        for i, chapter in enumerate(chapters, 1):
            try:
                print(f"📄 Глава {i}/{len(chapters)}: {chapter['title']}")
                
                content = self.get_chapter_content(chapter['url'])
                
                # Сохраняем главу
                chapter_filename = f"chapter_{chapter['number']:03d}_{chapter['chapter_id']}.txt"
                chapter_path = os.path.join(book_dir, chapter_filename)
                
                with open(chapter_path, 'w', encoding='utf-8') as f:
                    f.write(f"{content['title']}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(content['content'])
                
                downloaded_chapters.append(chapter)
                book_info['parsed_chapters'] += 1
                
                # Обновляем book_info после каждой главы
                with open(book_info_path, 'w', encoding='utf-8') as f:
                    json.dump(book_info, f, ensure_ascii=False, indent=2)
                
                # Пауза между запросами
                self._delay_between_requests()
                
            except Exception as e:
                print(f"❌ Ошибка при скачивании главы {chapter['title']}: {e}")
                failed_chapters.append({'chapter': chapter, 'error': str(e)})
        
        # Результаты
        results = {
            'book_info': book_info,
            'downloaded_chapters': len(downloaded_chapters),
            'failed_chapters': len(failed_chapters),
            'success_rate': len(downloaded_chapters) / len(chapters) if chapters else 0,
            'output_directory': book_dir
        }
        
        print(f"✅ Скачивание завершено:")
        print(f"   📖 Книга: {book_info['title']}")
        print(f"   📄 Скачано глав: {len(downloaded_chapters)}/{len(chapters)}")
        print(f"   📊 Успешность: {results['success_rate']:.1%}")
        print(f"   📁 Сохранено в: {book_dir}")
        
        return results
    
    def _delay_between_requests(self):
        """
        Пауза между запросами (может быть переопределена в дочерних классах)
        """
        time.sleep(1.0)
    
    def _get_page_content(self, url: str, timeout: int = 10, description: str = "") -> Optional[str]:
        """
        Базовый метод для получения содержимого страницы
        
        Args:
            url: URL страницы
            timeout: Таймаут запроса
            description: Описание запроса для логирования
            
        Returns:
            HTML содержимое страницы или None при ошибке
        """
        try:
            self.request_count += 1
            
            if description:
                print(f"🌐 {description}: {url}")
            
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            
            self.success_count += 1
            return response.text
            
        except Exception as e:
            print(f"❌ Ошибка запроса к {url}: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """
        Получить статистику работы парсера
        
        Returns:
            Dict со статистикой
        """
        success_rate = (self.success_count / self.request_count) if self.request_count > 0 else 0
        
        return {
            'source': self.source_name,
            'total_requests': self.request_count,
            'successful_requests': self.success_count,
            'success_rate': success_rate,
            'failed_requests': self.request_count - self.success_count
        }
    
    def reset_stats(self):
        """
        Сбросить статистику
        """
        self.request_count = 0
        self.success_count = 0
    
    def close(self):
        """
        Закрыть сессию
        """
        if self.session:
            self.session.close()
    
    def __enter__(self):
        """
        Контекстный менеджер - вход
        """
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Контекстный менеджер - выход
        """
        self.close()