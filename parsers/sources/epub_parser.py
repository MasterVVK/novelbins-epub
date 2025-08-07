#!/usr/bin/env python3
"""
EPUB Parser - Парсер для EPUB файлов
Извлекает главы и контент из EPUB файлов
"""
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

from ..base.base_parser import BaseParser

logger = logging.getLogger(__name__)


class EPUBParser(BaseParser):
    """
    Парсер для EPUB файлов
    Извлекает главы и контент из EPUB архива
    """
    
    def __init__(self, epub_path: str = None, auth_cookies: str = None, socks_proxy: str = None, max_chapters: Optional[int] = None, start_chapter: Optional[int] = None):
        """
        Инициализация EPUB парсера
        
        Args:
            epub_path: Путь к EPUB файлу
            auth_cookies: Не используется для EPUB (для совместимости)
            socks_proxy: Не используется для EPUB (для совместимости)
            max_chapters: Максимальное количество глав для извлечения
            start_chapter: Номер главы, с которой начать парсинг (1-based)
        """
        super().__init__('epub')
        self.epub_path = epub_path
        self.epub_data = {}
        self.chapters = []
        self.max_chapters = max_chapters
        self.start_chapter = start_chapter or 1
        
        logger.info(f"EPUBParser инициализирован: start_chapter={self.start_chapter}, max_chapters={self.max_chapters}")
        
        if epub_path:
            self.load_epub(epub_path)
    
    def load_epub(self, epub_path: str) -> bool:
        """
        Загрузить и разобрать EPUB файл
        
        Args:
            epub_path: Путь к EPUB файлу
            
        Returns:
            True если успешно загружен
        """
        try:
            if not os.path.exists(epub_path):
                logger.error(f"EPUB файл не найден: {epub_path}")
                return False
            
            # Проверяем размер файла
            file_size = os.path.getsize(epub_path)
            max_size = 100 * 1024 * 1024  # 100MB
            if file_size > max_size:
                logger.error(f"EPUB файл слишком большой: {file_size / 1024 / 1024:.1f}MB")
                return False
            
            self.epub_path = epub_path
            
            with zipfile.ZipFile(epub_path, 'r') as epub_zip:
                # Проверяем, что это действительно EPUB
                if 'META-INF/container.xml' not in epub_zip.namelist():
                    logger.error("Файл не содержит META-INF/container.xml")
                    return False
                
                # Читаем container.xml для получения пути к OPF файлу
                try:
                    container_xml = epub_zip.read('META-INF/container.xml')
                    container_tree = ET.fromstring(container_xml)
                except Exception as e:
                    logger.error(f"Ошибка чтения container.xml: {e}")
                    return False
                
                # Находим OPF файл
                rootfile = container_tree.find('.//{*}rootfile')
                if rootfile is None:
                    logger.error("Не найден rootfile в container.xml")
                    return False
                
                opf_path = rootfile.get('full-path')
                if not opf_path:
                    logger.error("Путь к OPF файлу не найден")
                    return False
                
                # Проверяем, что OPF файл существует
                if opf_path not in epub_zip.namelist():
                    logger.error(f"OPF файл не найден: {opf_path}")
                    return False
                
                # Читаем OPF файл
                try:
                    opf_content = epub_zip.read(opf_path)
                    opf_tree = ET.fromstring(opf_content)
                except Exception as e:
                    logger.error(f"Ошибка чтения OPF файла: {e}")
                    return False
                
                # Извлекаем метаданные
                self._extract_metadata(opf_tree)
                
                # Извлекаем манифест (список файлов)
                manifest = self._extract_manifest(opf_tree, epub_zip, opf_path)
                
                # Извлекаем spine (порядок чтения)
                spine = self._extract_spine(opf_tree)
                
                if not spine:
                    logger.warning("Spine пуст, попытка найти HTML файлы в манифесте")
                    # Если spine пуст, ищем HTML файлы в манифесте
                    html_items = [item_id for item_id, item in manifest.items() 
                                if item.get('media_type') in ['application/xhtml+xml', 'text/html']]
                    spine = html_items
                
                # Извлекаем главы
                self._extract_chapters(manifest, spine, epub_zip)
                
                if not self.chapters:
                    logger.warning("Не удалось извлечь главы из EPUB")
                    return False
                
                logger.info(f"EPUB успешно загружен: {len(self.chapters)} глав")
                return True
                
        except zipfile.BadZipFile:
            logger.error("Файл не является корректным ZIP архивом")
            return False
        except Exception as e:
            logger.error(f"Ошибка загрузки EPUB: {e}")
            return False
    
    def _extract_metadata(self, opf_tree: ET.Element):
        """Извлечение метаданных из OPF"""
        metadata = opf_tree.find('.//{*}metadata')
        if metadata is None:
            return
        
        self.epub_data['metadata'] = {}
        
        # Название
        title_elem = metadata.find('.//{*}title')
        if title_elem is not None:
            self.epub_data['metadata']['title'] = title_elem.text or ''
        
        # Автор
        creator_elem = metadata.find('.//{*}creator')
        if creator_elem is not None:
            self.epub_data['metadata']['author'] = creator_elem.text or ''
        
        # Описание
        description_elem = metadata.find('.//{*}description')
        if description_elem is not None:
            self.epub_data['metadata']['description'] = description_elem.text or ''
        
        # Язык
        language_elem = metadata.find('.//{*}language')
        if language_elem is not None:
            self.epub_data['metadata']['language'] = language_elem.text or 'en'
    
    def _extract_manifest(self, opf_tree: ET.Element, epub_zip: zipfile.ZipFile, opf_path: str) -> Dict:
        """Извлечение манифеста (списка файлов)"""
        manifest = {}
        manifest_elem = opf_tree.find('.//{*}manifest')
        
        if manifest_elem is None:
            return manifest
        
        opf_dir = os.path.dirname(opf_path)
        
        for item in manifest_elem.findall('.//{*}item'):
            item_id = item.get('id')
            href = item.get('href')
            media_type = item.get('media-type')
            
            if item_id and href:
                # Полный путь к файлу
                full_path = os.path.join(opf_dir, href) if opf_dir else href
                manifest[item_id] = {
                    'href': href,
                    'full_path': full_path,
                    'media_type': media_type
                }
        
        return manifest
    
    def _extract_spine(self, opf_tree: ET.Element) -> List[str]:
        """Извлечение spine (порядка чтения)"""
        spine = []
        spine_elem = opf_tree.find('.//{*}spine')
        
        if spine_elem is None:
            return spine
        
        for itemref in spine_elem.findall('.//{*}itemref'):
            idref = itemref.get('idref')
            if idref:
                spine.append(idref)
        
        return spine
    
    def _extract_chapters(self, manifest: Dict, spine: List[str], epub_zip: zipfile.ZipFile):
        """Извлечение глав из EPUB"""
        self.chapters = []
        html_chapter_count = 0  # Счетчик HTML глав (реальных глав)
        extracted_count = 0
        
        logger.info(f"Начинаем извлечение глав. start_chapter={self.start_chapter}, max_chapters={self.max_chapters}")
        logger.info(f"Всего элементов в spine: {len(spine)}")
        
        for item_id in spine:
            if item_id not in manifest:
                logger.warning(f"Элемент {item_id} не найден в манифесте")
                continue
            
            item = manifest[item_id]
            media_type = item.get('media_type', '')
            
            # Обрабатываем только HTML/XHTML файлы
            if media_type not in ['application/xhtml+xml', 'text/html']:
                logger.debug(f"Пропускаем элемент {item_id} с типом {media_type}")
                continue
            
            # Увеличиваем счетчик HTML глав
            html_chapter_count += 1
            
            # Логирование для отладки
            logger.info(f"HTML глава #{html_chapter_count}: {item_id} ({item.get('href', 'no href')})")
            
            # Пропускаем главы до start_chapter
            if html_chapter_count < self.start_chapter:
                logger.info(f"  -> Пропускаем (меньше start_chapter={self.start_chapter})")
                continue
            
            logger.info(f"  -> Извлекаем главу")
            
            # Проверяем ограничение на количество глав
            if self.max_chapters and extracted_count >= self.max_chapters:
                logger.info(f"Достигнут лимит глав: {self.max_chapters}")
                break
            
            try:
                full_path = item['full_path']
                
                # Проверяем, что файл существует в архиве
                if full_path not in epub_zip.namelist():
                    logger.warning(f"Файл {full_path} не найден в EPUB архиве")
                    continue
                
                # Читаем содержимое файла
                try:
                    content = epub_zip.read(full_path).decode('utf-8')
                except UnicodeDecodeError:
                    # Пробуем другие кодировки
                    try:
                        content = epub_zip.read(full_path).decode('latin-1')
                    except:
                        logger.warning(f"Не удалось декодировать файл {full_path}")
                        continue
                
                # Парсим HTML контент, используем номер главы из EPUB (html_chapter_count)
                result_chapter_number = html_chapter_count
                chapter_info = self._parse_html_content(content, result_chapter_number)
                if chapter_info:
                    self.chapters.append(chapter_info)
                    extracted_count += 1
                else:
                    logger.warning(f"Не удалось извлечь контент из главы {item_id}")
                    
            except Exception as e:
                logger.warning(f"Ошибка извлечения главы {item_id}: {e}")
                continue
        
        skipped_info = f" (пропущено первых: {self.start_chapter - 1})" if self.start_chapter > 1 else ""
        limit_info = f" (лимит: {self.max_chapters})" if self.max_chapters else ""
        logger.info(f"Извлечено глав: {len(self.chapters)}{skipped_info}{limit_info}")
    
    def _parse_html_content(self, html_content: str, chapter_number: int) -> Optional[Dict]:
        """Парсинг HTML контента главы"""
        try:
            # Простой парсинг HTML с помощью регулярных выражений
            # Удаляем XML декларацию и DOCTYPE
            html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content)
            html_content = re.sub(r'<!DOCTYPE[^>]*>', '', html_content)
            
            # Извлекаем заголовок - сначала пробуем h2, потом h1, потом title
            h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', html_content, re.IGNORECASE | re.DOTALL)
            if h2_match:
                title = re.sub(r'<[^>]+>', '', h2_match.group(1)).strip()
            else:
                h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.IGNORECASE | re.DOTALL)
                if h1_match:
                    title = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
                else:
                    title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
                    title = title_match.group(1).strip() if title_match else f"Глава {chapter_number}"
            
            # Извлекаем содержимое body
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.IGNORECASE | re.DOTALL)
            if not body_match:
                return None
            
            body_content = body_match.group(1)
            
            # Очищаем HTML теги, оставляя только текст
            content = self._clean_html_content(body_content)
            
            if not content.strip():
                return None
            
            return {
                'number': chapter_number,
                'title': title,
                'content': content,
                'chapter_id': f"chapter_{chapter_number}",
                'url': f"chapter_{chapter_number}",  # Добавляем URL для совместимости
                'word_count': len(content.split())
            }
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга HTML контента: {e}")
            return None
    
    def _clean_html_content(self, html_content: str) -> str:
        """Очистка HTML контента от тегов"""
        # Удаляем скрипты и стили
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
        
        # Заменяем некоторые теги на переносы строк
        html_content = re.sub(r'</?(?:p|div|br|h[1-6])[^>]*>', '\n', html_content, flags=re.IGNORECASE)
        
        # Удаляем все остальные HTML теги
        html_content = re.sub(r'<[^>]+>', '', html_content)
        
        # Декодируем HTML сущности
        html_content = html_content.replace('&nbsp;', ' ')
        html_content = html_content.replace('&amp;', '&')
        html_content = html_content.replace('&lt;', '<')
        html_content = html_content.replace('&gt;', '>')
        html_content = html_content.replace('&quot;', '"')
        html_content = html_content.replace('&#39;', "'")
        
        # Очищаем лишние пробелы и переносы строк
        lines = [line.strip() for line in html_content.split('\n')]
        lines = [line for line in lines if line]
        
        return '\n\n'.join(lines)
    
    def get_book_info(self, book_url: str = None) -> Dict:
        """
        Получить информацию о книге
        
        Args:
            book_url: Не используется для EPUB (для совместимости)
            
        Returns:
            Dict с информацией о книге
        """
        metadata = self.epub_data.get('metadata', {})
        
        return {
            'title': metadata.get('title', 'Неизвестная книга'),
            'author': metadata.get('author', 'Неизвестный автор'),
            'description': metadata.get('description', ''),
            'status': 'completed',  # EPUB уже завершен
            'genre': '',
            'book_id': os.path.basename(self.epub_path) if self.epub_path else 'epub_book',
            'total_chapters': len(self.chapters),
            'language': metadata.get('language', 'en'),
            'source_type': 'epub',
            'epub_path': self.epub_path
        }
    
    def get_chapter_list(self, book_url: str = None) -> List[Dict]:
        """
        Получить список глав книги
        
        Args:
            book_url: Не используется для EPUB (для совместимости)
            
        Returns:
            List[Dict] со списком глав
        """
        return self.chapters
    
    def get_chapter_content(self, chapter_url: str) -> Dict:
        """
        Получить содержимое главы
        
        Args:
            chapter_url: URL или ID главы
            
        Returns:
            Dict с содержимым главы
        """
        # Извлекаем номер главы из URL или ID
        if chapter_url.startswith('chapter_'):
            chapter_id = chapter_url
        else:
            # Пытаемся извлечь номер из URL
            match = re.search(r'chapter[_-]?(\d+)', chapter_url, re.IGNORECASE)
            if match:
                chapter_number = int(match.group(1))
                chapter_id = f"chapter_{chapter_number}"
            else:
                raise ValueError(f"Не удается определить номер главы из URL: {chapter_url}")
        
        # Ищем главу по ID
        for chapter in self.chapters:
            if chapter['chapter_id'] == chapter_id:
                return {
                    'title': chapter['title'],
                    'content': chapter['content'],
                    'chapter_id': chapter['chapter_id'],
                    'chapter_number': chapter['number'],
                    'word_count': chapter['word_count']
                }
        
        raise ValueError(f"Глава {chapter_id} не найдена")
    
    def download_book(self, book_url: str = None, output_dir: str = None, chapter_limit: Optional[int] = None) -> Dict:
        """
        Скачать книгу (для EPUB это просто копирование файла)
        
        Args:
            book_url: Не используется для EPUB
            output_dir: Директория для сохранения
            chapter_limit: Не используется для EPUB
            
        Returns:
            Dict с результатами
        """
        if not self.epub_path:
            raise ValueError("EPUB файл не загружен")
        
        if not output_dir:
            output_dir = os.getcwd()
        
        # Создаем директорию если не существует
        os.makedirs(output_dir, exist_ok=True)
        
        # Копируем EPUB файл
        import shutil
        output_path = os.path.join(output_dir, os.path.basename(self.epub_path))
        shutil.copy2(self.epub_path, output_path)
        
        return {
            'success': True,
            'output_path': output_path,
            'total_chapters': len(self.chapters),
            'downloaded_chapters': len(self.chapters)
        }
    
    def get_stats(self) -> Dict:
        """Получить статистику парсера"""
        return {
            'source': 'epub',
            'epub_path': self.epub_path,
            'total_chapters': len(self.chapters),
            'request_count': self.request_count,
            'success_count': self.success_count
        } 