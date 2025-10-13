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
        query = Chapter.query.filter_by(novel_id=novel_id)
        
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

    def _format_chapter_title(self, chapter_number: int, title: str, prefix_mode: str = 'auto', prefix_text: str = 'Глава') -> str:
        """Форматирование заголовка главы с учетом настроек префикса
        
        Args:
            chapter_number: Номер главы
            title: Исходный заголовок
            prefix_mode: Режим добавления префикса ('always', 'never', 'auto')
            prefix_text: Текст префикса (по умолчанию 'Глава')
        """
        import re
        
        if prefix_mode == 'never':
            # Никогда не добавляем префикс
            return title
        
        elif prefix_mode == 'always':
            # Всегда добавляем префикс
            return f"{prefix_text} {chapter_number}: {title}"
        
        else:  # auto mode
            # Проверяем, начинается ли заголовок уже с "Глава X:" или "Chapter X:" или подобного
            patterns = [
                r'^(Глава|Chapter|Часть|Part)\s*\d+[:\s]',  # Различные языки
                r'^第\s*\d+\s*[章回]',  # Китайский формат (第100章 или 第100回)
                r'^\d+\.\s',  # Начинается с "1. "
                r'^\d+:\s',    # Начинается с "1: "
            ]
            
            for pattern in patterns:
                if re.match(pattern, title, re.IGNORECASE):
                    # Заголовок уже содержит номер главы, возвращаем как есть
                    return title
            
            # Заголовок не содержит номер, добавляем префикс
            return f"{prefix_text} {chapter_number}: {title}"
    
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
        
        # Получаем настройки префикса для этой новеллы
        prefix_mode = novel.epub_add_chapter_prefix or 'auto'
        prefix_text = novel.epub_chapter_prefix_text or 'Глава'

        # Создаём книгу
        book = epub.EpubBook()

        # Метаданные
        timestamp = datetime.now().strftime("%Y%m%d")
        book.set_identifier(f'{novel.title.lower().replace(" ", "-")}-{timestamp}')
        book.set_title(novel.title)
        book.set_language('ru')
        book.add_author(novel.author or 'Неизвестный автор')

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
            edit_info_page = self._create_edit_info_page(chapters, prefix_mode, prefix_text)
            book.add_item(edit_info_page)

        # Создаём оглавление
        toc_page = self._create_toc_page(chapters, prefix_mode, prefix_text)
        book.add_item(toc_page)

        # Список для навигации
        toc_list = []
        spine_list = ['nav', title_page]

        if any(ch['is_edited'] for ch in chapters):
            spine_list.append(edit_info_page)

        spine_list.append(toc_page)

        # Добавляем главы
        for chapter in chapters:
            ch = self._create_chapter_page(chapter, nav_css, prefix_mode, prefix_text)
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
                Автор: {novel.author or 'Неизвестный автор'}
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

    def _create_edit_info_page(self, chapters: List[Dict], prefix_mode: str = 'auto', prefix_text: str = 'Глава') -> epub.EpubHtml:
        """Создание страницы с информацией о редактировании"""
        edited_chapters = [ch for ch in chapters if ch['is_edited']]
        
        chapters_info = ""
        for ch in edited_chapters:
            quality_text = f" (качество: {ch['quality_score']}/10)" if ch['quality_score'] else ""
            formatted_title = self._format_chapter_title(ch['number'], ch['title'], prefix_mode, prefix_text)
            chapters_info += f"<div class='toc-item'>{formatted_title}{quality_text}</div>"

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

    def _create_toc_page(self, chapters: List[Dict], prefix_mode: str = 'auto', prefix_text: str = 'Глава') -> epub.EpubHtml:
        """Создание оглавления"""
        toc_items = ""
        for ch in chapters:
            edited_class = " toc-edited" if ch['is_edited'] else ""
            formatted_title = self._format_chapter_title(ch['number'], ch['title'], prefix_mode, prefix_text)
            toc_items += f"<div class='toc-item toc-chapter{edited_class}'>{formatted_title}</div>"

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

    def _create_chapter_page(self, chapter: Dict, nav_css: epub.EpubItem, prefix_mode: str = 'auto', prefix_text: str = 'Глава') -> epub.EpubHtml:
        """Создание страницы главы"""
        # Конвертируем markdown в HTML
        content_html = self._convert_markdown_to_html(chapter['content'])
        
        # Форматируем заголовок с учетом настроек
        formatted_title = self._format_chapter_title(chapter['number'], chapter['title'], prefix_mode, prefix_text)
        
        # Добавляем информацию о качестве если глава отредактирована
        quality_html = ""
        #if chapter['is_edited'] and chapter.get('quality_score'):
        #    quality_html = f'<div class="quality-score">Качество редактуры: {chapter["quality_score"]}/10</div>'

        chapter_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{formatted_title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h2 class="chapter-title">{formatted_title}</h2>
            {content_html}
            {quality_html}
        </body>
        </html>
        """
        
        chapter_page = epub.EpubHtml(
            title=formatted_title,
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

    def create_bilingual_epub(self, novel_id: int, chapters: List[Dict], config: Optional[EPUBConfig] = None) -> str:
        """
        Создание двуязычного EPUB файла с чередованием русского перевода и китайского оригинала

        Args:
            novel_id: ID новеллы
            chapters: Список глав с данными
            config: Конфигурация EPUB

        Returns:
            Путь к созданному EPUB файлу
        """
        if not epub:
            raise ImportError("Модуль ebooklib не установлен")

        from app.models import Novel
        from app import db
        from app.utils.text_alignment import BilingualTextAligner

        # Получаем информацию о новелле
        novel = Novel.query.get(novel_id)
        if not novel:
            raise ValueError(f"Новелла с ID {novel_id} не найдена")

        # Создаём книгу
        book = epub.EpubBook()

        # Метаданные
        timestamp = datetime.now().strftime("%Y%m%d")
        book.set_identifier(f'{novel.title.lower().replace(" ", "-")}-bilingual-{timestamp}')
        book.set_title(f"{novel.title} (双语版 / Bilingual)")
        book.set_language('ru')
        book.add_author(novel.author or 'Неизвестный автор')

        # Добавляем описание
        book.add_metadata('DC', 'description',
            f'Двуязычное издание романа "{novel.title}" с чередованием русского перевода и китайского оригинала.')

        # CSS стили для двуязычного формата
        style = self._get_bilingual_css_styles()

        # Добавляем CSS
        nav_css = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=style
        )
        book.add_item(nav_css)

        # Создаём титульную страницу
        title_page = self._create_bilingual_title_page(novel)
        book.add_item(title_page)

        # Создаём страницу с информацией о формате
        info_page = self._create_bilingual_info_page()
        book.add_item(info_page)

        # Создаём оглавление
        toc_page = self._create_bilingual_toc_page(chapters)
        book.add_item(toc_page)

        # Список для навигации
        toc_list = []
        spine_list = ['nav', title_page, info_page, toc_page]

        # Добавляем главы
        for chapter in chapters:
            ch = self._create_bilingual_chapter_page(chapter, nav_css, novel_id)
            book.add_item(ch)
            spine_list.append(ch)
            toc_list.append(ch)

        # Настройка навигации
        toc_sections = [
            epub.Link('title.xhtml', 'Титульная страница', 'title'),
            epub.Link('info.xhtml', 'О формате', 'info'),
            epub.Link('toc.xhtml', 'Оглавление', 'toc'),
            (epub.Section('Главы'), toc_list[:len(chapters)])
        ]

        book.toc = tuple(toc_sections)

        # Добавляем NCX и Nav файлы
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # spine
        book.spine = spine_list

        # Определяем путь для сохранения
        chapters_range = f"{chapters[0]['number']}-{chapters[-1]['number']}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        filename = f"{novel.title.replace(' ', '_')}_bilingual_{chapters_range}_{timestamp}.epub"
        epub_path = self.epub_dir / filename

        # Сохраняем EPUB
        epub.write_epub(str(epub_path), book, {})

        return str(epub_path)

    def _get_bilingual_css_styles(self) -> str:
        """CSS стили для двуязычного EPUB"""
        return """
        @namespace epub "http://www.idpf.org/2007/ops";

        body {
            font-family: "Noto Sans", "Source Han Sans", "Arial", sans-serif;
            font-size: 1.1em;
            line-height: 1.8;
            margin: 2em;
            text-align: left;
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

        .russian-sentence {
            font-family: "Times New Roman", "Georgia", serif;
            font-size: 1.1em;
            line-height: 1.6;
            margin: 0.8em 0;
            text-indent: 1.5em;
            color: #2c3e50;
        }

        .chinese-sentence {
            font-family: "Noto Serif CJK SC", "Source Han Serif SC", "SimSun", serif;
            font-size: 1.05em;
            line-height: 1.8;
            margin: 0.5em 0 1.2em 0;
            text-indent: 2em;
            color: #555;
            background-color: #f8f9fa;
            padding: 0.3em 0.5em;
            border-left: 3px solid #e0e0e0;
        }

        .chapter-title {
            font-size: 1.3em;
            font-weight: bold;
            text-align: center;
            margin: 2em 0 1em 0;
            color: #2c3e50;
        }

        .toc-item {
            margin: 0.5em 0;
            text-indent: 0;
        }

        .toc-chapter {
            font-weight: bold;
        }

        .info-box {
            background-color: #e8f5e8;
            padding: 1em;
            margin: 1em 0;
            border-radius: 5px;
            border-left: 4px solid #27ae60;
        }

        .parallel-row {
            display: flex;
            margin: 1em 0;
        }

        .russian-column {
            flex: 1;
            padding-right: 1em;
            border-right: 1px solid #ddd;
        }

        .chinese-column {
            flex: 1;
            padding-left: 1em;
            font-family: "Noto Serif CJK SC", "Source Han Serif SC", "SimSun", serif;
        }
        """

    def _create_bilingual_title_page(self, novel) -> epub.EpubHtml:
        """Создание титульной страницы для двуязычного EPUB"""
        title_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{novel.title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>{novel.title}</h1>
            <h2 style="text-align: center; font-size: 1.1em; font-weight: normal; margin-top: -1em;">
                双语版 / Bilingual Edition
            </h2>
            <p style="text-align: center; font-size: 1.2em; margin: 2em 0;">
                Автор: {novel.author or 'Неизвестный автор'}
            </p>
            <p style="text-align: center; margin: 2em 0;">
                Русский перевод + китайский оригинал<br>
                Russian Translation + Chinese Original<br>
                Создано: {datetime.now().strftime('%d.%m.%Y')}
            </p>
            <div style="text-align: center; margin: 4em 0;">
                <p style="font-size: 0.9em; color: #7f8c8d;">
                    Этот EPUB файл был автоматически сгенерирован<br>
                    системой перевода и редактирования<br>
                    для удобного изучения китайского языка
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

        return title_page

    def _create_bilingual_info_page(self) -> epub.EpubHtml:
        """Создание страницы с информацией о двуязычном формате"""
        content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>О формате</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>О двуязычном формате</h1>
            <div class="info-box">
                <h3>Как читать эту книгу</h3>
                <p>Эта книга представлена в двуязычном формате для изучения китайского языка:</p>
                <ul>
                    <li><strong>Русский перевод</strong> - отредактированный литературный перевод</li>
                    <li><strong>中文原文</strong> - оригинальный китайский текст</li>
                </ul>

                <h3>Формат чередования</h3>
                <p>Предложения чередуются: сначала русский перевод, затем китайский оригинал.</p>
                <p>Это позволяет:</p>
                <ul>
                    <li>Читать и понимать сюжет на русском языке</li>
                    <li>Сразу видеть оригинальный текст на китайском</li>
                    <li>Пассивно запоминать иероглифы в контексте</li>
                    <li>Постепенно привыкать к структуре китайских предложений</li>
                </ul>

                <h3>Рекомендации по чтению</h3>
                <p>Для эффективного изучения языка рекомендуется:</p>
                <ul>
                    <li>Сначала прочитать русский перевод</li>
                    <li>Затем посмотреть на китайский оригинал</li>
                    <li>Попытаться найти знакомые иероглифы</li>
                    <li>Не зацикливаться на непонятных словах - продолжайте читать</li>
                </ul>

                <p style="margin-top: 2em; font-style: italic; color: #666;">
                    Приятного чтения и успехов в изучении китайского языка! 加油！
                </p>
            </div>
        </body>
        </html>
        """

        info_page = epub.EpubHtml(
            title='О формате',
            file_name='info.xhtml',
            content=content
        )

        return info_page

    def _create_bilingual_toc_page(self, chapters: List[Dict]) -> epub.EpubHtml:
        """Создание оглавления для двуязычного EPUB"""
        toc_items = []
        for ch in chapters:
            toc_items.append(
                f'<div class="toc-item toc-chapter">'
                f'<a href="chapter_{ch["number"]:03d}.xhtml">Глава {ch["number"]}: {ch["title"]}</a>'
                f'</div>'
            )

        content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Оглавление</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>Оглавление / 目录</h1>
            {''.join(toc_items)}
        </body>
        </html>
        """

        toc_page = epub.EpubHtml(
            title='Оглавление',
            file_name='toc.xhtml',
            content=content
        )

        return toc_page

    def _create_bilingual_chapter_page(self, chapter: Dict, nav_css: epub.EpubItem, novel_id: int) -> epub.EpubHtml:
        """Создание страницы главы с двуязычным содержимым"""
        from app.utils.text_alignment import BilingualTextAligner
        from app.models import Chapter
        from app import db

        # Получаем полный объект главы из базы данных (по novel_id И chapter_number!)
        db_chapter = Chapter.query.filter_by(
            novel_id=novel_id,
            chapter_number=chapter['number']
        ).first()

        logger.info(f"📖 Создание двуязычной главы {chapter['number']}: novel_id={novel_id}")

        if not db_chapter:
            logger.warning(f"⚠️  Глава {chapter['number']} не найдена в БД для novel_id={novel_id}")
            content_html = f'<p class="russian-sentence">{chapter["content"]}</p>'
        elif not db_chapter.original_text:
            logger.warning(f"⚠️  Глава {chapter['number']}: нет оригинального текста (original_text пуст)")
            logger.info(f"   Заголовок главы: {db_chapter.original_title}")
            content_html = f'<p class="russian-sentence">{chapter["content"]}</p>'
        else:
            # Выравниваем русский перевод и китайский оригинал
            russian_text = chapter['content']
            chinese_text = db_chapter.original_text

            logger.info(f"✅ Глава {chapter['number']}: найден оригинал ({len(chinese_text)} символов)")
            logger.info(f"   Заголовок: {db_chapter.original_title}")
            logger.info(f"   Перевод: {len(russian_text)} символов")

            # Разбиваем на предложения и выравниваем
            aligned_pairs = BilingualTextAligner.align_sentences(russian_text, chinese_text)
            logger.info(f"   Выровнено {len(aligned_pairs)} пар предложений")

            # Форматируем для EPUB (чередование)
            content_html = BilingualTextAligner.format_for_epub(
                aligned_pairs,
                mode='sentence',
                style='alternating'
            )

        chapter_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Глава {chapter['number']}: {chapter['title']}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h2 class="chapter-title">Глава {chapter['number']}: {chapter['title']}</h2>
            {content_html}
        </body>
        </html>
        """

        chapter_page = epub.EpubHtml(
            title=f"Глава {chapter['number']}: {chapter['title']}",
            file_name=f'chapter_{chapter["number"]:03d}.xhtml',
            content=chapter_content
        )
        chapter_page.add_item(nav_css)

        return chapter_page 