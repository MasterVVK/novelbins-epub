#!/usr/bin/env python3
"""
Скрипт для анализа EPUB файла и извлечения первых 10 глав
"""

import sys
import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional
import logging

# Настройка логирования
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Простая реализация EPUBParser без зависимостей от других модулей
class SimplifiedEPUBParser:
    """Упрощенный парсер EPUB для анализа"""
    
    def __init__(self, epub_path: str, max_chapters: Optional[int] = None):
        self.epub_path = epub_path
        self.max_chapters = max_chapters
        self.epub_data = {}
        self.chapters = []
        
        if epub_path:
            self.load_epub(epub_path)
    
    def load_epub(self, epub_path: str) -> bool:
        """Загрузить и разобрать EPUB файл"""
        try:
            if not os.path.exists(epub_path):
                logger.error(f"EPUB файл не найден: {epub_path}")
                return False
            
            with zipfile.ZipFile(epub_path, 'r') as epub_zip:
                # Проверяем, что это действительно EPUB
                if 'META-INF/container.xml' not in epub_zip.namelist():
                    logger.error("Файл не содержит META-INF/container.xml")
                    return False
                
                # Читаем container.xml для получения пути к OPF файлу
                container_xml = epub_zip.read('META-INF/container.xml')
                container_tree = ET.fromstring(container_xml)
                
                # Находим OPF файл
                rootfile = container_tree.find('.//{*}rootfile')
                if rootfile is None:
                    logger.error("Не найден rootfile в container.xml")
                    return False
                
                opf_path = rootfile.get('full-path')
                if not opf_path:
                    logger.error("Путь к OPF файлу не найден")
                    return False
                
                # Читаем OPF файл
                opf_content = epub_zip.read(opf_path)
                opf_tree = ET.fromstring(opf_content)
                
                # Извлекаем метаданные
                self._extract_metadata(opf_tree)
                
                # Извлекаем манифест (список файлов)
                manifest = self._extract_manifest(opf_tree, epub_zip, opf_path)
                
                # Извлекаем spine (порядок чтения)
                spine = self._extract_spine(opf_tree)
                
                if not spine:
                    # Если spine пуст, ищем HTML файлы в манифесте
                    html_items = [item_id for item_id, item in manifest.items() 
                                if item.get('media_type') in ['application/xhtml+xml', 'text/html']]
                    spine = html_items
                
                # Извлекаем главы
                self._extract_chapters(manifest, spine, epub_zip)
                
                return len(self.chapters) > 0
                
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
        chapter_number = 1
        extracted_count = 0
        
        for item_id in spine:
            # Проверяем ограничение на количество глав
            if self.max_chapters and extracted_count >= self.max_chapters:
                break
            
            if item_id not in manifest:
                continue
            
            item = manifest[item_id]
            media_type = item.get('media_type', '')
            
            # Обрабатываем только HTML/XHTML файлы
            if media_type not in ['application/xhtml+xml', 'text/html']:
                continue
            
            try:
                full_path = item['full_path']
                
                # Проверяем, что файл существует в архиве
                if full_path not in epub_zip.namelist():
                    continue
                
                # Читаем содержимое файла
                try:
                    content = epub_zip.read(full_path).decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        content = epub_zip.read(full_path).decode('latin-1')
                    except:
                        continue
                
                # Парсим HTML контент
                chapter_info = self._parse_html_content(content, chapter_number)
                if chapter_info:
                    self.chapters.append(chapter_info)
                    chapter_number += 1
                    extracted_count += 1
                    
            except Exception as e:
                continue
    
    def _parse_html_content(self, html_content: str, chapter_number: int) -> Optional[Dict]:
        """Парсинг HTML контента главы"""
        try:
            # Простой парсинг HTML с помощью регулярных выражений
            html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content)
            html_content = re.sub(r'<!DOCTYPE[^>]*>', '', html_content)
            
            # Извлекаем заголовок
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
                'word_count': len(content.split())
            }
            
        except Exception as e:
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
    
    def get_book_info(self) -> Dict:
        """Получить информацию о книге"""
        metadata = self.epub_data.get('metadata', {})
        
        return {
            'title': metadata.get('title', 'Неизвестная книга'),
            'author': metadata.get('author', 'Неизвестный автор'),
            'description': metadata.get('description', ''),
            'language': metadata.get('language', 'en'),
            'total_chapters': len(self.chapters)
        }


def analyze_content_style(content: str) -> dict:
    """Анализ стиля и особенностей текста"""
    
    # Длина текста
    word_count = len(content.split())
    char_count = len(content)
    
    # Анализ структуры предложений
    sentences = re.split(r'[.!?]+', content)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
    
    # Типы знаков препинания
    punctuation_analysis = {
        'exclamation_marks': content.count('!'),
        'question_marks': content.count('?'),
        'ellipsis': len(re.findall(r'\.{3,}', content)),
        'dashes': content.count('—') + content.count('--'),
        'quotation_marks': content.count('"') + content.count('"') + content.count('"')
    }
    
    # Диалоги (предполагаем, что строки в кавычках - диалоги)
    dialogue_lines = len(re.findall(r'[""«»"\'`].+?[""«»"\']', content))
    
    # Повторяющиеся слова/фразы (исключая служебные)
    words = re.findall(r'\b\w+\b', content.lower())
    stop_words = {'и', 'в', 'на', 'с', 'по', 'для', 'от', 'до', 'из', 'к', 'у', 'о', 'об', 'за', 'под', 'над', 'при', 'через', 'между', 'без', 'я', 'ты', 'он', 'она', 'оно', 'мы', 'вы', 'они', 'этот', 'эта', 'это', 'эти', 'тот', 'та', 'то', 'те', 'который', 'которая', 'которое', 'которые', 'что', 'как', 'где', 'когда', 'почему', 'зачем', 'куда', 'откуда', 'сколько', 'чей', 'чья', 'чьё', 'чьи', 'не', 'ни', 'да', 'нет', 'уже', 'еще', 'ещё', 'только', 'лишь', 'даже', 'вот', 'вон', 'здесь', 'там', 'тут', 'сюда', 'туда', 'сейчас', 'теперь', 'тогда', 'потом', 'затем', 'сначала', 'сперва', 'снова', 'опять', 'again', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'among', 'throughout', 'despite', 'towards', 'upon', 'within', 'without', 'against', 'his', 'her', 'its', 'their', 'our', 'your', 'my', 'this', 'that', 'these', 'those', 'who', 'whom', 'whose', 'which', 'what', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just', 'should', 'now', 'than', 'also', 'back', 'other', 'many', 'much', 'well', 'may'}
    
    content_words = [w for w in words if len(w) > 2 and w not in stop_words]
    word_freq = Counter(content_words)
    most_common_words = word_freq.most_common(10)
    
    return {
        'word_count': word_count,
        'character_count': char_count,
        'sentence_count': len(sentences),
        'avg_sentence_length': round(avg_sentence_length, 1),
        'punctuation_analysis': punctuation_analysis,
        'dialogue_lines': dialogue_lines,
        'most_common_words': most_common_words,
        'writing_style': {
            'descriptive_ratio': (punctuation_analysis['exclamation_marks'] + punctuation_analysis['ellipsis']) / max(word_count / 100, 1),
            'dialogue_ratio': dialogue_lines / max(len(sentences), 1) * 100,
            'complexity_score': avg_sentence_length / 10  # простая метрика сложности
        }
    }


def extract_entities(text: str) -> dict:
    """Извлечение персонажей, локаций и терминов"""
    
    # Имена персонажей (слова с заглавной буквы, встречающиеся часто)
    capitalized_words = re.findall(r'\b[A-ZА-Я][a-zа-я]+\b', text)
    name_counter = Counter(capitalized_words)
    
    # Исключаем слова, которые часто встречаются в начале предложений
    common_sentence_starters = {'И', 'В', 'На', 'С', 'По', 'Для', 'От', 'До', 'Из', 'К', 'У', 'О', 'Об', 'За', 'Под', 'Над', 'При', 'Через', 'Между', 'Без', 'Он', 'Она', 'Оно', 'Мы', 'Вы', 'Они', 'Этот', 'Эта', 'Это', 'Эти', 'Тот', 'Та', 'То', 'Те', 'Который', 'Которая', 'Которое', 'Которые', 'Что', 'Как', 'Где', 'Когда', 'Но', 'А', 'Да', 'Нет', 'Уже', 'Еще', 'Только', 'Лишь', 'Даже', 'Вот', 'Вон', 'Здесь', 'Там', 'Тут', 'The', 'And', 'But', 'Or', 'So', 'Then', 'Now', 'Here', 'There', 'This', 'That', 'These', 'Those', 'When', 'Where', 'Why', 'How', 'What', 'Who', 'Which'}
    
    potential_names = {name: count for name, count in name_counter.most_common(20) 
                      if count > 2 and name not in common_sentence_starters and len(name) > 2}
    
    # Локации (часто идут после предлогов)
    location_patterns = [
        r'(?:в|на|из|к|от|до|около|рядом с|возле)\s+([А-ЯA-Z][а-яa-z]+(?:\s+[А-ЯA-Z][а-яa-z]+)*)',
        r'(?:in|at|to|from|near|around)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
    ]
    
    locations = []
    for pattern in location_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        locations.extend(matches)
    
    location_counter = Counter(locations)
    
    # Термины - слова, которые пишутся с заглавной буквы в середине предложения
    sentences = re.split(r'[.!?]+', text)
    terms = []
    
    for sentence in sentences:
        words = sentence.strip().split()
        if len(words) > 1:  # пропускаем первое слово предложения
            for word in words[1:]:
                # Ищем слова с заглавной буквы в середине предложения
                if re.match(r'^[A-ZА-Я][a-zа-я]+$', word) and len(word) > 3:
                    terms.append(word)
    
    term_counter = Counter(terms)
    
    return {
        'characters': dict(potential_names),
        'locations': dict(location_counter.most_common(10)),
        'terms': dict(term_counter.most_common(15))
    }


def analyze_epub_file(epub_path: str, max_chapters: int = 10):
    """Основная функция анализа EPUB файла"""
    
    print(f"Анализ EPUB файла: {epub_path}")
    print("=" * 60)
    
    # Инициализация парсера с лимитом глав
    parser = SimplifiedEPUBParser(epub_path=epub_path, max_chapters=max_chapters)
    
    if not parser.chapters:
        print("❌ Не удалось загрузить EPUB файл или извлечь главы")
        return
    
    # Получение информации о книге
    book_info = parser.get_book_info()
    
    print("📚 ИНФОРМАЦИЯ О ПРОИЗВЕДЕНИИ")
    print("-" * 40)
    print(f"Название: {book_info['title']}")
    print(f"Автор: {book_info['author']}")
    print(f"Описание: {book_info['description'][:200]}{'...' if len(book_info['description']) > 200 else ''}")
    print(f"Язык: {book_info['language']}")
    print(f"Всего глав в файле: {book_info['total_chapters']}")
    print(f"Анализируемых глав: {len(parser.chapters)}")
    print()
    
    # Анализ глав
    print("📖 ПЕРВЫЕ 10 ГЛАВ")
    print("-" * 40)
    
    all_content = ""
    chapter_analyses = []
    
    for i, chapter in enumerate(parser.chapters, 1):
        print(f"\n{i}. {chapter['title']}")
        print(f"   Слов: {chapter['word_count']}")
        
        # Показываем начало главы (первые 200 символов)
        content_preview = chapter['content'][:300].replace('\n', ' ')
        print(f"   Начало: {content_preview}{'...' if len(chapter['content']) > 300 else ''}")
        
        # Добавляем к общему контенту для анализа
        all_content += "\n\n" + chapter['content']
        
        # Анализируем стиль каждой главы
        chapter_analysis = analyze_content_style(chapter['content'])
        chapter_analyses.append(chapter_analysis)
    
    print("\n")
    
    # Общий анализ стиля
    print("🎨 АНАЛИЗ СТИЛЯ И ОСОБЕННОСТЕЙ")
    print("-" * 40)
    
    overall_analysis = analyze_content_style(all_content)
    
    print(f"Общее количество слов: {overall_analysis['word_count']:,}")
    print(f"Общее количество символов: {overall_analysis['character_count']:,}")
    print(f"Количество предложений: {overall_analysis['sentence_count']:,}")
    print(f"Средняя длина предложения: {overall_analysis['avg_sentence_length']} слов")
    
    print(f"\nПунктуация:")
    punct = overall_analysis['punctuation_analysis']
    print(f"  - Восклицательные знаки: {punct['exclamation_marks']}")
    print(f"  - Вопросительные знаки: {punct['question_marks']}")
    print(f"  - Многоточия: {punct['ellipsis']}")
    print(f"  - Тире: {punct['dashes']}")
    print(f"  - Кавычки: {punct['quotation_marks']}")
    
    print(f"\nСтиль письма:")
    style = overall_analysis['writing_style']
    print(f"  - Экспрессивность: {style['descriptive_ratio']:.1f} (восклицания/многоточия на 100 слов)")
    print(f"  - Доля диалогов: {style['dialogue_ratio']:.1f}%")
    print(f"  - Сложность текста: {style['complexity_score']:.1f}/10")
    
    # Анализ сущностей
    print("\n🔍 КЛЮЧЕВЫЕ ПЕРСОНАЖИ, ЛОКАЦИИ И ТЕРМИНЫ")
    print("-" * 40)
    
    entities = extract_entities(all_content)
    
    print("Персонажи (по частоте упоминания):")
    for name, count in sorted(entities['characters'].items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {name}: {count} упоминаний")
    
    if entities['locations']:
        print(f"\nЛокации:")
        for location, count in sorted(entities['locations'].items(), key=lambda x: x[1], reverse=True)[:8]:
            print(f"  - {location}: {count} упоминаний")
    
    if entities['terms']:
        print(f"\nВажные термины:")
        for term, count in sorted(entities['terms'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  - {term}: {count} упоминаний")
    
    # Наиболее частые слова
    print(f"\nНаиболее частые значимые слова:")
    for word, count in overall_analysis['most_common_words'][:15]:
        print(f"  - {word}: {count}")
    
    # Анализ прогрессии по главам
    print("\n📊 СТАТИСТИКА ПО ГЛАВАМ")
    print("-" * 40)
    
    total_words = sum(analysis['word_count'] for analysis in chapter_analyses)
    avg_words_per_chapter = total_words / len(chapter_analyses)
    
    print(f"Средняя длина главы: {avg_words_per_chapter:.0f} слов")
    
    shortest_chapter = min(chapter_analyses, key=lambda x: x['word_count'])
    longest_chapter = max(chapter_analyses, key=lambda x: x['word_count'])
    
    shortest_idx = chapter_analyses.index(shortest_chapter) + 1
    longest_idx = chapter_analyses.index(longest_chapter) + 1
    
    print(f"Самая короткая глава: #{shortest_idx} ({shortest_chapter['word_count']} слов)")
    print(f"Самая длинная глава: #{longest_idx} ({longest_chapter['word_count']} слов)")
    
    # Прогрессия сложности
    complexity_scores = [analysis['writing_style']['complexity_score'] for analysis in chapter_analyses]
    avg_complexity = sum(complexity_scores) / len(complexity_scores)
    print(f"Средняя сложность текста: {avg_complexity:.1f}/10")
    
    print("\n✅ Анализ завершен!")


if __name__ == "__main__":
    epub_file_path = "/home/user/novelbins-epub/web_app/instance/epub_files/qinkan.net.epub"
    
    if not os.path.exists(epub_file_path):
        print(f"❌ EPUB файл не найден: {epub_file_path}")
        sys.exit(1)
    
    analyze_epub_file(epub_file_path, max_chapters=10)