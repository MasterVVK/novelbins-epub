"""
EPUB Service - Сервис для генерации EPUB файлов
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
import sqlite3
import logging

# Добавляем путь к корневой папке проекта для импорта модулей
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from ebooklib import epub
    from models import EPUBConfig
    from database import DatabaseManager
except ImportError as e:
    logging.error(f"Ошибка импорта модулей для EPUB: {e}")
    epub = None
    EPUBConfig = None
    DatabaseManager = None

logger = logging.getLogger(__name__)


class EPUBService:
    """Сервис для генерации EPUB файлов"""

    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Инициализация с Flask приложением"""
        self.app = app
        # Создаем папку для EPUB файлов
        self.epub_dir = Path(app.instance_path) / 'epub_output'
        self.epub_dir.mkdir(exist_ok=True)

    def get_edited_chapters_from_db(self, novel_id: int, chapter_numbers: Optional[List[int]] = None) -> List[Dict]:
        """Получение отредактированных глав из базы данных web_app"""
        from app.models import Chapter, Translation
        from app import db

        # Получаем главы новеллы
        query = Chapter.query.filter_by(novel_id=novel_id, is_active=True)
        
        if chapter_numbers:
            query = query.filter(Chapter.chapter_number.in_(chapter_numbers))
        
        chapters = query.order_by(Chapter.chapter_number).all()
        
        result = []
        edited_count = 0

        for chapter in chapters:
            # Получаем лучший перевод (отредактированный или исходный)
            edited_translation = chapter.edited_translation
            current_translation = chapter.current_translation
            
            if edited_translation:
                # Используем отредактированную версию
                final_text = edited_translation.translated_text
                final_title = edited_translation.translated_title
                is_edited = True
                quality_score = edited_translation.quality_score
            elif current_translation:
                # Используем исходный перевод
                final_text = current_translation.translated_text
                final_title = current_translation.translated_title
                is_edited = False
                quality_score = None
            else:
                # Пропускаем главы без перевода
                continue

            if is_edited:
                edited_count += 1

            result.append({
                'number': chapter.chapter_number,
                'title': final_title or f"Глава {chapter.chapter_number}",
                'content': final_text,
                'summary': current_translation.summary if current_translation else None,
                'is_edited': is_edited,
                'quality_score': quality_score
            })

        logger.info(f"Загружено глав: {len(result)}, отредактировано: {edited_count}")
        return result

    def create_epub(self, novel_id: int, chapters: List[Dict], config: Optional[EPUBConfig] = None) -> str:
        """Создание EPUB файла"""
        if not epub:
            raise ImportError("Модуль ebooklib не установлен")

        from app.models import Novel
        from app import db

        # Получаем информацию о новелле
        novel = Novel.query.get(novel_id)
        if not novel:
            raise ValueError(f"Новелла с ID {novel_id} не найдена")

        # Создаём книгу
        book = epub.EpubBook()

        # Метаданные
        timestamp = datetime.now().strftime("%Y%m%d")
        book.set_identifier(f'{novel.title.lower().replace(" ", "-")}-{timestamp}')
        book.set_title(novel.title)
        book.set_language('ru')
        book.add_author(novel.config.get('author', 'Неизвестный автор'))

        # Добавляем описание
        book.add_metadata('DC', 'description',
            f'Перевод романа "{novel.title}" с редакторской правкой.')

        # CSS стили
        style = self._get_css_styles()

        # Добавляем CSS
        nav_css = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=style
        )
        book.add_item(nav_css)

        # Создаём титульную страницу
        title_page = self._create_title_page(novel)
        book.add_item(title_page)

        # Создаём страницу с информацией о редактировании
        if any(ch['is_edited'] for ch in chapters):
            edit_info_page = self._create_edit_info_page(chapters)
            book.add_item(edit_info_page)

        # Создаём оглавление
        toc_page = self._create_toc_page(chapters)
        book.add_item(toc_page)

        # Список для навигации
        toc_list = []
        spine_list = ['nav', title_page]

        if any(ch['is_edited'] for ch in chapters):
            spine_list.append(edit_info_page)

        spine_list.append(toc_page)

        # Добавляем главы
        for chapter in chapters:
            ch = self._create_chapter_page(chapter, nav_css)
            book.add_item(ch)
            spine_list.append(ch)
            toc_list.append(ch)

        # Настройка навигации
        toc_sections = [
            epub.Link('title.xhtml', 'Титульная страница', 'title'),
        ]

        if any(ch['is_edited'] for ch in chapters):
            toc_sections.append(epub.Link('edit_info.xhtml', 'Информация о редактировании', 'edit_info'))

        toc_sections.extend([
            epub.Link('toc.xhtml', 'Оглавление', 'toc'),
            (epub.Section('Главы'), toc_list[:len(chapters)])
        ])

        book.toc = tuple(toc_sections)

        # Добавляем NCX и Nav файлы
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # spine
        book.spine = spine_list

        # Определяем путь для сохранения
        chapters_range = f"{chapters[0]['number']}-{chapters[-1]['number']}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Добавляем пометку если есть отредактированные главы
        edited_mark = "_edited" if any(ch['is_edited'] for ch in chapters) else ""

        filename = f"{novel.title.replace(' ', '_')}_{chapters_range}{edited_mark}_{timestamp}.epub"
        epub_path = self.epub_dir / filename

        # Сохраняем EPUB
        epub.write_epub(str(epub_path), book, {})
        
        return str(epub_path)

    def _get_css_styles(self) -> str:
        """CSS стили для EPUB"""
        return """
        @namespace epub "http://www.idpf.org/2007/ops";

        body {
            font-family: "Times New Roman", serif;
            font-size: 1.1em;
            line-height: 1.6;
            margin: 2em;
            text-align: justify;
        }

        h1 {
            font-size: 1.8em;
            text-align: center;
            margin-bottom: 2em;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5em;
        }

        h2 {
            font-size: 1.4em;
            text-align: center;
            margin: 1.5em 0;
            color: #34495e;
        }

        h3 {
            font-size: 1.2em;
            margin: 1em 0;
            color: #2c3e50;
        }

        p {
            margin: 0.8em 0;
            text-indent: 1.5em;
        }

        .chapter-title {
            font-size: 1.3em;
            font-weight: bold;
            text-align: center;
            margin: 2em 0 1em 0;
            color: #2c3e50;
        }

        .summary {
            font-style: italic;
            background-color: #f8f9fa;
            padding: 1em;
            margin: 1em 0;
            border-left: 4px solid #3498db;
        }

        .quality-score {
            font-size: 0.9em;
            color: #7f8c8d;
            text-align: right;
            margin-top: 1em;
        }

        .toc-item {
            margin: 0.5em 0;
        }

        .toc-chapter {
            font-weight: bold;
        }

        .toc-edited {
            color: #27ae60;
        }

        .edit-info {
            background-color: #e8f5e8;
            padding: 1em;
            margin: 1em 0;
            border-radius: 5px;
        }
        """

    def _create_title_page(self, novel) -> epub.EpubHtml:
        """Создание титульной страницы"""
        title_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{novel.title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>{novel.title}</h1>
            <p style="text-align: center; font-size: 1.2em; margin: 2em 0;">
                Автор: {novel.config.get('author', 'Неизвестный автор')}
            </p>
            <p style="text-align: center; margin: 2em 0;">
                Перевод с китайского языка<br>
                Создано: {datetime.now().strftime('%d.%m.%Y')}
            </p>
            <div style="text-align: center; margin: 4em 0;">
                <p style="font-size: 0.9em; color: #7f8c8d;">
                    Этот EPUB файл был автоматически сгенерирован<br>
                    системой перевода и редактирования
                </p>
            </div>
        </body>
        </html>
        """
        
        title_page = epub.EpubHtml(
            title='Титульная страница',
            file_name='title.xhtml',
            content=title_content
        )
        title_page.add_item(epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=self._get_css_styles()
        ))
        
        return title_page

    def _create_edit_info_page(self, chapters: List[Dict]) -> epub.EpubHtml:
        """Создание страницы с информацией о редактировании"""
        edited_chapters = [ch for ch in chapters if ch['is_edited']]
        
        chapters_info = ""
        for ch in edited_chapters:
            quality_text = f" (качество: {ch['quality_score']}/10)" if ch['quality_score'] else ""
            chapters_info += f"<div class='toc-item'>Глава {ch['number']}: {ch['title']}{quality_text}</div>"

        content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Информация о редактировании</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>Информация о редактировании</h1>
            <div class="edit-info">
                <p>В этом EPUB файле {len(edited_chapters)} глав были отредактированы для улучшения качества перевода.</p>
                <p>Отредактированные главы:</p>
                {chapters_info}
            </div>
        </body>
        </html>
        """
        
        edit_info_page = epub.EpubHtml(
            title='Информация о редактировании',
            file_name='edit_info.xhtml',
            content=content
        )
        edit_info_page.add_item(epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=self._get_css_styles()
        ))
        
        return edit_info_page

    def _create_toc_page(self, chapters: List[Dict]) -> epub.EpubHtml:
        """Создание оглавления"""
        toc_items = ""
        for ch in chapters:
            edited_class = " toc-edited" if ch['is_edited'] else ""
            toc_items += f"<div class='toc-item toc-chapter{edited_class}'>Глава {ch['number']}: {ch['title']}</div>"

        content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Оглавление</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>Оглавление</h1>
            {toc_items}
        </body>
        </html>
        """
        
        toc_page = epub.EpubHtml(
            title='Оглавление',
            file_name='toc.xhtml',
            content=content
        )
        toc_page.add_item(epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=self._get_css_styles()
        ))
        
        return toc_page

    def _create_chapter_page(self, chapter: Dict, nav_css: epub.EpubItem) -> epub.EpubHtml:
        """Создание страницы главы"""
        # Конвертируем markdown в HTML
        content_html = self._convert_markdown_to_html(chapter['content'])
        
        # Добавляем резюме если есть
        summary_html = ""
        if chapter.get('summary'):
            summary_html = f'<div class="summary"><strong>Резюме:</strong> {chapter["summary"]}</div>'

        # Добавляем информацию о качестве если глава отредактирована
        quality_html = ""
        if chapter['is_edited'] and chapter.get('quality_score'):
            quality_html = f'<div class="quality-score">Качество редактуры: {chapter["quality_score"]}/10</div>'

        chapter_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{chapter['title']}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h2 class="chapter-title">{chapter['title']}</h2>
            {summary_html}
            {content_html}
            {quality_html}
        </body>
        </html>
        """
        
        chapter_page = epub.EpubHtml(
            title=chapter['title'],
            file_name=f'chapter_{chapter["number"]:03d}.xhtml',
            content=chapter_content
        )
        chapter_page.add_item(nav_css)
        
        return chapter_page

    def _convert_markdown_to_html(self, text: str) -> str:
        """Простая конвертация markdown в HTML"""
        if not text:
            return ""
        
        # Заменяем переносы строк на параграфы
        paragraphs = text.split('\n\n')
        html_paragraphs = []
        
        for p in paragraphs:
            p = p.strip()
            if p:
                # Простая обработка жирного текста
                p = p.replace('**', '<strong>').replace('**', '</strong>')
                p = p.replace('*', '<em>').replace('*', '</em>')
                html_paragraphs.append(f'<p>{p}</p>')
        
        return '\n'.join(html_paragraphs) 