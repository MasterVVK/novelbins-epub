#!/usr/bin/env python3
"""
Детальный анализ китайского EPUB файла с извлечением фактического содержимого глав
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

class ChineseEPUBParser:
    """Парсер для китайских EPUB файлов"""
    
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
        
        # Получаем все файлы из архива для анализа
        all_files = epub_zip.namelist()
        print(f"Всего файлов в EPUB: {len(all_files)}")
        
        # Ищем HTML/XHTML файлы, которые могут содержать главы
        html_files = [f for f in all_files if f.endswith(('.html', '.xhtml', '.htm'))]
        print(f"HTML файлов найдено: {len(html_files)}")
        
        # Пытаемся извлечь главы из spine
        for item_id in spine:
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
                        content = epub_zip.read(full_path).decode('gb2312')
                    except:
                        try:
                            content = epub_zip.read(full_path).decode('gbk')
                        except:
                            continue
                
                # Парсим HTML контент
                chapter_info = self._parse_html_content(content, chapter_number, full_path)
                if chapter_info and len(chapter_info['content'].strip()) > 50:  # Только главы с достаточным содержимым
                    self.chapters.append(chapter_info)
                    chapter_number += 1
                    extracted_count += 1
                    
            except Exception as e:
                continue
    
    def _parse_html_content(self, html_content: str, chapter_number: int, file_path: str) -> Optional[Dict]:
        """Парсинг HTML контента главы"""
        try:
            # Простой парсинг HTML с помощью регулярных выражений
            html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content)
            html_content = re.sub(r'<!DOCTYPE[^>]*>', '', html_content)
            
            # Извлекаем заголовок из title или из первого h1/h2/h3
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""
            
            # Если заголовок пустой или слишком общий, ищем в h1-h3
            if not title or title in ['Cover', 'Table Of Contents']:
                h_match = re.search(r'<h[1-3][^>]*>(.*?)</h[1-3]>', html_content, re.IGNORECASE | re.DOTALL)
                if h_match:
                    title = self._clean_html_tags(h_match.group(1).strip())
            
            if not title:
                title = f"第{chapter_number}章"
            
            # Извлекаем содержимое body
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.IGNORECASE | re.DOTALL)
            if not body_match:
                # Если нет body, берем весь контент
                body_content = html_content
            else:
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
                'word_count': len(content),  # Для китайского текста считаем символы
                'file_path': file_path
            }
            
        except Exception as e:
            return None
    
    def _clean_html_tags(self, text: str) -> str:
        """Очистка HTML тегов из текста"""
        # Удаляем все HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        # Декодируем HTML сущности
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        return text.strip()
    
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
        lines = [line for line in lines if line and not line.startswith('www.') and not line.startswith('Txt,Epub,Mobi')]
        
        return '\n\n'.join(lines)
    
    def get_book_info(self) -> Dict:
        """Получить информацию о книге"""
        metadata = self.epub_data.get('metadata', {})
        
        return {
            'title': metadata.get('title', 'Неизвестная книга'),
            'author': metadata.get('author', 'Неизвестный автор'),
            'description': metadata.get('description', ''),
            'language': metadata.get('language', 'zh-CN'),
            'total_chapters': len(self.chapters)
        }


def analyze_chinese_names(text: str) -> dict:
    """Анализ китайских имен и терминов"""
    
    # Ищем китайские имена (обычно 2-3 символа)
    chinese_names = re.findall(r'[\u4e00-\u9fff]{2,3}(?=[\u4e00-\u9fff\s，。！？]|$)', text)
    name_counter = Counter(chinese_names)
    
    # Исключаем общие слова и фразы
    common_words = {'这个', '那个', '什么', '怎么', '为什么', '不是', '就是', '可是', '但是', '然后', '因为', '所以', '如果', '虽然', '虽然', '虽說', '无论', '不管', '之后', '以后', '之前', '以前', '现在', '未来', '时候', '地方', '东西', '事情', '问题', '办法', '方法', '样子', '样子'}
    
    # Фильтруем имена (убираем слишком общие слова)
    potential_names = {name: count for name, count in name_counter.most_common(20) 
                      if count > 1 and name not in common_words and len(name) >= 2}
    
    # Ищем титулы и звания
    titles = re.findall(r'[\u4e00-\u9fff]*(?:师|师傅|师兄|师姐|师叔|师伯|师祖|长老|宗主|掌门|弟子|门人)[\u4e00-\u9fff]*', text)
    title_counter = Counter(titles)
    
    # Ищем места и локации
    locations = re.findall(r'[\u4e00-\u9fff]*(?:山|峰|谷|洞|府|宗|门|城|国|域|界|地|岛)[\u4e00-\u9fff]*', text)
    location_counter = Counter(locations)
    
    return {
        'characters': dict(potential_names),
        'titles': dict(title_counter.most_common(10)),
        'locations': dict(location_counter.most_common(10))
    }


def analyze_chinese_text_style(content: str) -> dict:
    """Анализ стиля китайского текста"""
    
    # Подсчет символов (для китайского текста)
    char_count = len(content)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    
    # Анализ структуры предложений (по знакам препинания)
    sentences = re.split(r'[。！？]', content)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_sentence_length = sum(len(s) for s in sentences) / len(sentences) if sentences else 0
    
    # Типы знаков препинания
    punctuation_analysis = {
        'periods': content.count('。'),
        'exclamation_marks': content.count('！'),
        'question_marks': content.count('？'),
        'commas': content.count('，'),
        'quotes': content.count('"') + content.count('"') + content.count('「') + content.count('」')
    }
    
    # Диалоги (строки в кавычках)
    dialogue_lines = len(re.findall(r'[""「」『』].+?[""「」『』]', content))
    
    return {
        'character_count': char_count,
        'chinese_character_count': chinese_chars,
        'chinese_ratio': chinese_chars / char_count if char_count > 0 else 0,
        'sentence_count': len(sentences),
        'avg_sentence_length': round(avg_sentence_length, 1),
        'punctuation_analysis': punctuation_analysis,
        'dialogue_lines': dialogue_lines,
        'writing_style': {
            'dialogue_ratio': dialogue_lines / max(len(sentences), 1) * 100,
            'complexity_score': avg_sentence_length / 20  # Адаптированная метрика для китайского
        }
    }


def analyze_chinese_epub(epub_path: str, max_chapters: int = 10):
    """Анализ китайского EPUB файла"""
    
    print(f"Анализ китайского EPUB файла: {epub_path}")
    print("=" * 80)
    
    # Инициализация парсера с лимитом глав
    parser = ChineseEPUBParser(epub_path=epub_path, max_chapters=max_chapters)
    
    if not parser.chapters:
        print("❌ Не удалось загрузить EPUB файл или извлечь главы")
        return
    
    # Получение информации о книге
    book_info = parser.get_book_info()
    
    print("📚 ИНФОРМАЦИЯ О ПРОИЗВЕДЕНИИ")
    print("-" * 50)
    print(f"Название: {book_info['title']} (我欲封天 - Я хочу запечатать небеса)")
    print(f"Автор: {book_info['author']} (вероятно, 耳根 - Ergen)")
    print(f"Жанр: Сянься (仙侠) - культивация/боевые искусства")
    print(f"Язык: {book_info['language']} (китайский)")
    print(f"Всего глав в файле: {book_info['total_chapters']}")
    print(f"Анализируемых глав: {len(parser.chapters)}")
    print()
    
    # Анализ глав
    print("📖 ПЕРВЫЕ 10 ГЛАВ")
    print("-" * 50)
    
    all_content = ""
    chapter_analyses = []
    
    for i, chapter in enumerate(parser.chapters, 1):
        print(f"\n{i}. {chapter['title']}")
        print(f"   Символов: {chapter['word_count']}")
        print(f"   Файл: {chapter['file_path']}")
        
        # Показываем начало главы (первые 200 символов)
        content_preview = chapter['content'][:200].replace('\n', ' ')
        print(f"   Начало: {content_preview}{'...' if len(chapter['content']) > 200 else ''}")
        
        # Добавляем к общему контенту для анализа
        all_content += "\n\n" + chapter['content']
        
        # Анализируем стиль каждой главы
        chapter_analysis = analyze_chinese_text_style(chapter['content'])
        chapter_analyses.append(chapter_analysis)
    
    print("\n")
    
    # Общий анализ стиля
    print("🎨 АНАЛИЗ СТИЛЯ И ОСОБЕННОСТЕЙ")
    print("-" * 50)
    
    overall_analysis = analyze_chinese_text_style(all_content)
    
    print(f"Общее количество символов: {overall_analysis['character_count']:,}")
    print(f"Китайские символы: {overall_analysis['chinese_character_count']:,} ({overall_analysis['chinese_ratio']:.1%})")
    print(f"Количество предложений: {overall_analysis['sentence_count']:,}")
    print(f"Средняя длина предложения: {overall_analysis['avg_sentence_length']} символов")
    
    print(f"\nПунктуация:")
    punct = overall_analysis['punctuation_analysis']
    print(f"  - Точки (。): {punct['periods']}")
    print(f"  - Восклицательные знаки (！): {punct['exclamation_marks']}")
    print(f"  - Вопросительные знаки (？): {punct['question_marks']}")
    print(f"  - Запятые (，): {punct['commas']}")
    print(f"  - Кавычки: {punct['quotes']}")
    
    print(f"\nСтиль письма:")
    style = overall_analysis['writing_style']
    print(f"  - Доля диалогов: {style['dialogue_ratio']:.1f}%")
    print(f"  - Сложность текста: {style['complexity_score']:.1f}/10")
    
    # Анализ персонажей и терминов
    print("\n🔍 КЛЮЧЕВЫЕ ПЕРСОНАЖИ, ЛОКАЦИИ И ТЕРМИНЫ")
    print("-" * 50)
    
    entities = analyze_chinese_names(all_content)
    
    print("Персонажи и имена (по частоте упоминания):")
    for name, count in sorted(entities['characters'].items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f"  - {name}: {count} упоминаний")
    
    if entities['titles']:
        print(f"\nТитулы и звания:")
        for title, count in sorted(entities['titles'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  - {title}: {count} упоминаний")
    
    if entities['locations']:
        print(f"\nЛокации и места:")
        for location, count in sorted(entities['locations'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  - {location}: {count} упоминаний")
    
    # Анализ прогрессии по главам
    print("\n📊 СТАТИСТИКА ПО ГЛАВАМ")
    print("-" * 50)
    
    total_chars = sum(analysis['character_count'] for analysis in chapter_analyses)
    avg_chars_per_chapter = total_chars / len(chapter_analyses)
    
    print(f"Средняя длина главы: {avg_chars_per_chapter:.0f} символов")
    
    shortest_chapter = min(chapter_analyses, key=lambda x: x['character_count'])
    longest_chapter = max(chapter_analyses, key=lambda x: x['character_count'])
    
    shortest_idx = chapter_analyses.index(shortest_chapter) + 1
    longest_idx = chapter_analyses.index(longest_chapter) + 1
    
    print(f"Самая короткая глава: #{shortest_idx} ({shortest_chapter['character_count']} символов)")
    print(f"Самая длинная глава: #{longest_idx} ({longest_chapter['character_count']} символов)")
    
    # Прогрессия сложности
    complexity_scores = [analysis['writing_style']['complexity_score'] for analysis in chapter_analyses]
    avg_complexity = sum(complexity_scores) / len(complexity_scores)
    print(f"Средняя сложность текста: {avg_complexity:.1f}/10")
    
    print("\n🎯 ЗАКЛЮЧЕНИЕ О ПРОИЗВЕДЕНИИ")
    print("-" * 50)
    print("• Жанр: Сянься - роман о культивации")
    print("• Сюжет: История о молодом человеке на пути к бессмертию")
    print("• Стиль: Классическая китайская фантастика с элементами боевых искусств")
    print("• Особенности: Типичная структура сянься с развитием персонажа через уровни силы")
    
    print("\n✅ Анализ завершен!")


if __name__ == "__main__":
    epub_file_path = "/home/user/novelbins-epub/web_app/instance/epub_files/qinkan.net.epub"
    
    if not os.path.exists(epub_file_path):
        print(f"❌ EPUB файл не найден: {epub_file_path}")
        sys.exit(1)
    
    analyze_chinese_epub(epub_file_path, max_chapters=10)