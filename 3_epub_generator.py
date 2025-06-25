"""
3_epub_generator.py - Генерация EPUB из отредактированных глав
"""
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
from ebooklib import epub
import sqlite3

from models import Chapter, EPUBConfig
from database import DatabaseManager


class EPUBGenerator:
    """Генератор EPUB файлов из отредактированных глав"""

    def __init__(self, config: EPUBConfig):
        self.config = config

    def get_edited_chapters_from_db(self, db_path: str, chapter_numbers: Optional[List[int]] = None) -> List[Dict]:
        """Получение отредактированных глав из базы данных"""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Проверяем наличие таблицы edited_chapters
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='edited_chapters'
        """)

        if not cursor.fetchone():
            print("❌ Таблица edited_chapters не найдена!")
            print("   Сначала запустите редактор: python 4_editor.py")
            conn.close()
            return []

        if chapter_numbers:
            placeholders = ','.join('?' * len(chapter_numbers))
            query = f"""
                SELECT 
                    c.chapter_number,
                    c.translated_title,
                    COALESCE(e.edited_text, c.translated_text) as final_text,
                    c.summary,
                    e.quality_score_after,
                    e.edited_at,
                    e.status as edit_status
                FROM chapters c
                LEFT JOIN edited_chapters e ON c.chapter_number = e.chapter_number
                WHERE c.status = 'completed' 
                    AND c.chapter_number IN ({placeholders})
                    AND (e.status = 'completed' OR e.status IS NULL)
                ORDER BY c.chapter_number
            """
            cursor.execute(query, chapter_numbers)
        else:
            # Берём все главы (переведённые + отредактированные если есть)
            query = """
                SELECT 
                    c.chapter_number,
                    c.translated_title,
                    COALESCE(e.edited_text, c.translated_text) as final_text,
                    c.summary,
                    e.quality_score_after,
                    e.edited_at,
                    e.status as edit_status
                FROM chapters c
                LEFT JOIN edited_chapters e ON c.chapter_number = e.chapter_number
                WHERE c.status = 'completed'
                    AND (e.status = 'completed' OR e.status IS NULL)
                ORDER BY c.chapter_number
            """
            cursor.execute(query)

        chapters = []
        edited_count = 0

        for row in cursor.fetchall():
            is_edited = row['edit_status'] == 'completed'
            if is_edited:
                edited_count += 1

            chapters.append({
                'number': row['chapter_number'],
                'title': row['translated_title'],
                'content': row['final_text'],
                'summary': row['summary'],
                'is_edited': is_edited,
                'quality_score': row['quality_score_after'] if is_edited else None
            })

        print(f"\n Загружено глав: {len(chapters)}")
        print(f"   Отредактировано: {edited_count}")
        print(f"   Только переведено: {len(chapters) - edited_count}")

        conn.close()
        return chapters

    def create_epub(self, chapters: List[Dict], glossary: dict = None) -> str:
        """Создание EPUB файла"""
        # Создаём книгу
        book = epub.EpubBook()

        # Метаданные
        book.set_identifier(f'shrouding-the-heavens-{datetime.now().strftime("%Y%m%d")}')
        book.set_title(self.config.book_title)
        book.set_language(self.config.book_language)
        book.add_author(self.config.book_author)

        # Добавляем описание
        book.add_metadata('DC', 'description',
            'Перевод романа "Shrouding the Heavens" (遮天) с редакторской правкой. '
            'В далёком космосе древний бронзовый гроб дрейфует в пустоте...')

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
        title_page = self._create_title_page()
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

        # Добавляем глоссарий если нужно
        if self.config.include_glossary and glossary:
            glossary_page = self._create_glossary_page(glossary, nav_css)
            if glossary_page:
                book.add_item(glossary_page)
                spine_list.append(glossary_page)
                toc_list.append(glossary_page)

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

        if self.config.include_glossary and glossary:
            toc_sections.append(epub.Link('glossary.xhtml', 'Глоссарий', 'glossary'))

        book.toc = tuple(toc_sections)

        # Добавляем NCX и Nav файлы
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # spine
        book.spine = spine_list

        # Определяем путь для сохранения
        output_dir = Path("epub_output")
        output_dir.mkdir(exist_ok=True)

        chapters_range = f"{chapters[0]['number']}-{chapters[-1]['number']}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Добавляем пометку если есть отредактированные главы
        edited_mark = "_edited" if any(ch['is_edited'] for ch in chapters) else ""

        output_path = output_dir / f"shrouding_the_heavens_ch{chapters_range}{edited_mark}_{timestamp}.epub"

        # Записываем EPUB файл
        epub.write_epub(output_path, book, {})

        return str(output_path)

    def _get_css_styles(self) -> str:
        """CSS стили для книги"""
        return '''
        @namespace epub "http://www.idpf.org/2007/ops";
        
        body {
            font-family: Georgia, serif;
            margin: 5%;
            text-align: justify;
            line-height: 1.6;
        }
        
        h1 {
            text-align: center;
            margin-top: 1em;
            margin-bottom: 1em;
            font-size: 1.5em;
            page-break-before: always;
        }
        
        h2 {
            text-align: center;
            margin-top: 2em;
            margin-bottom: 1em;
            font-size: 1.3em;
        }
        
        h3 {
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            font-size: 1.1em;
        }
        
        p {
            text-indent: 1.5em;
            margin-top: 0;
            margin-bottom: 0.5em;
        }
        
        .chapter-number {
            text-align: center;
            font-size: 0.9em;
            color: #666;
            margin-bottom: 0.5em;
        }
        
        .first-paragraph {
            text-indent: 0;
        }
        
        .summary {
            font-style: italic;
            color: #555;
            margin: 1em 0;
            padding: 1em;
            border-left: 3px solid #ccc;
        }
        
        .glossary-section {
            margin-top: 2em;
        }
        
        .glossary-item {
            margin: 0.5em 0;
            text-indent: 0;
        }
        
        .glossary-term {
            font-weight: bold;
        }
        
        .toc-link {
            text-indent: 0;
            margin: 0.5em 0;
        }
        
        .edit-info {
            margin: 2em 0;
            padding: 1em;
            background-color: #f5f5f5;
            border: 1px solid #ddd;
        }
        
        .quality-mark {
            font-size: 0.8em;
            color: #666;
            font-style: italic;
        }
        '''

    def _create_title_page(self) -> epub.EpubHtml:
        """Создание титульной страницы"""
        title_page = epub.EpubHtml(
            title='Титульная страница',
            file_name='title.xhtml',
            lang='ru'
        )

        title_page.content = f'''
        <html xmlns="http://www.w3.org/1999/xhtml">
        <head>
            <title>{self.config.book_title}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <div style="text-align: center; margin-top: 30%;">
                <h1 style="font-size: 2.5em; margin-bottom: 0.5em;">{self.config.book_title}</h1>
                <h2 style="font-size: 1.2em; font-weight: normal;">Shrouding the Heavens</h2>
                <h2 style="font-size: 1em; font-weight: normal;">遮天</h2>
                <p style="margin-top: 2em;">Автор: {self.config.book_author}</p>
                <p style="margin-top: 1em; font-size: 0.9em;">Перевод с английского</p>
                <p style="margin-top: 0.5em; font-size: 0.9em;">С редакторской правкой</p>
                <p style="margin-top: 3em; font-size: 0.8em;">{datetime.now().year}</p>
            </div>
        </body>
        </html>
        '''

        return title_page

    def _create_edit_info_page(self, chapters: List[Dict]) -> epub.EpubHtml:
        """Создание страницы с информацией о редактировании"""
        edit_page = epub.EpubHtml(
            title='Информация о редактировании',
            file_name='edit_info.xhtml',
            lang='ru'
        )

        edited_count = sum(1 for ch in chapters if ch['is_edited'])
        avg_quality = sum(ch['quality_score'] for ch in chapters if ch['quality_score']) / edited_count if edited_count > 0 else 0

        edit_page.content = f'''
        <html xmlns="http://www.w3.org/1999/xhtml">
        <head>
            <title>Информация о редактировании</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>Информация о редактировании</h1>
            <div class="edit-info">
                <p>Данное издание содержит текст, прошедший литературную редактуру для улучшения читабельности.</p>
                
                <h3>Статистика редактирования:</h3>
                <ul>
                    <li>Всего глав в книге: {len(chapters)}</li>
                    <li>Отредактировано: {edited_count}</li>
                    <li>Средняя оценка качества после редактуры: {avg_quality:.1f}/10</li>
                </ul>
                
                <h3>Что было улучшено:</h3>
                <ul>
                    <li>Стилистика и литературность текста</li>
                    <li>Естественность диалогов</li>
                    <li>Исправлены грамматические ошибки</li>
                    <li>Улучшена читабельность</li>
                    <li>Сохранён дух оригинального произведения</li>
                </ul>
                
                <p style="margin-top: 2em; font-style: italic;">
                    Отредактированные главы помечены знаком ✎ в оглавлении.
                </p>
            </div>
        </body>
        </html>
        '''

        return edit_page

    def _create_toc_page(self, chapters: List[Dict]) -> epub.EpubHtml:
        """Создание страницы оглавления"""
        toc_page = epub.EpubHtml(
            title='Оглавление',
            file_name='toc.xhtml',
            lang='ru'
        )

        toc_links = []
        for chapter in chapters:
            ch_filename = f'chapter_{chapter["number"]:03d}.xhtml'
            # Добавляем пометку для отредактированных глав
            edit_mark = ' ✎' if chapter['is_edited'] else ''
            toc_links.append(f'<p class="toc-link"><a href="{ch_filename}">{chapter["title"]}{edit_mark}</a></p>')

        toc_content = '''
        <html xmlns="http://www.w3.org/1999/xhtml">
        <head>
            <title>Оглавление</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>Оглавление</h1>
            <p style="text-align: center; font-style: italic; margin-bottom: 2em;">
                ✎ — главы с редакторской правкой
            </p>
            ''' + '\n'.join(toc_links) + '''
        </body>
        </html>
        '''

        toc_page.content = toc_content
        return toc_page

    def _create_chapter_page(self, chapter: Dict, nav_css: epub.EpubItem) -> epub.EpubHtml:
        """Создание страницы главы"""
        ch_filename = f'chapter_{chapter["number"]:03d}.xhtml'
        ch = epub.EpubHtml(
            title=chapter['title'],
            file_name=ch_filename,
            lang='ru'
        )

        # Форматируем контент главы
        paragraphs = chapter['content'].split('\n\n')
        formatted_paragraphs = []

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if para:
                if i == 0:
                    formatted_paragraphs.append(f'<p class="first-paragraph">{para}</p>')
                else:
                    formatted_paragraphs.append(f'<p>{para}</p>')

        # Убираем номер главы из заголовка для отображения
        display_title = chapter['title'].replace(f"Глава {chapter['number']}: ", "")

        # HTML содержимое главы
        ch_content = f'''
        <html xmlns="http://www.w3.org/1999/xhtml">
        <head>
            <title>{chapter['title']}</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <div class="chapter-number">Глава {chapter['number']}</div>
            <h1>{display_title}</h1>
        '''

        # Добавляем пометку о качестве для отредактированных глав
        if chapter['is_edited'] and chapter['quality_score']:
            ch_content += f'''
            <p class="quality-mark">Качество редактуры: {chapter['quality_score']}/10</p>
            '''

        # Добавляем резюме если включено
        if self.config.include_summaries and chapter['summary']:
            ch_content += f'''
            <div class="summary">
                <p><em>Резюме предыдущей главы:</em></p>
                <p>{chapter['summary']}</p>
            </div>
            '''

        ch_content += '\n'.join(formatted_paragraphs)
        ch_content += '''
        </body>
        </html>
        '''

        ch.content = ch_content
        ch.add_item(nav_css)

        return ch

    def _create_glossary_page(self, glossary: dict, nav_css: epub.EpubItem) -> Optional[epub.EpubHtml]:
        """Создание страницы глоссария"""
        if not any(glossary.values()):
            return None

        glossary_page = epub.EpubHtml(
            title='Глоссарий',
            file_name='glossary.xhtml',
            lang='ru'
        )

        content = '''
        <html xmlns="http://www.w3.org/1999/xhtml">
        <head>
            <title>Глоссарий</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>Глоссарий</h1>
        '''

        if glossary.get('characters'):
            content += '''
            <div class="glossary-section">
                <h2>Персонажи</h2>
            '''
            for eng, rus in sorted(glossary['characters'].items()):
                content += f'<p class="glossary-item"><span class="glossary-term">{eng}</span> — {rus}</p>\n'
            content += '</div>'

        if glossary.get('locations'):
            content += '''
            <div class="glossary-section">
                <h2>Локации</h2>
            '''
            for eng, rus in sorted(glossary['locations'].items()):
                content += f'<p class="glossary-item"><span class="glossary-term">{eng}</span> — {rus}</p>\n'
            content += '</div>'

        if glossary.get('terms'):
            content += '''
            <div class="glossary-section">
                <h2>Термины</h2>
            '''
            for eng, rus in sorted(glossary['terms'].items()):
                content += f'<p class="glossary-item"><span class="glossary-term">{eng}</span> — {rus}</p>\n'
            content += '</div>'

        content += '''
        </body>
        </html>
        '''

        glossary_page.content = content
        glossary_page.add_item(nav_css)

        return glossary_page


def main():
    """Основная функция генератора EPUB"""
    parser = argparse.ArgumentParser(description='Генератор EPUB из отредактированных глав')
    parser.add_argument('-c', '--chapters', nargs='+', type=int,
                       help='Номера глав для включения в EPUB (по умолчанию все)')
    parser.add_argument('--no-glossary', action='store_true',
                       help='Не включать глоссарий')
    parser.add_argument('--include-summaries', action='store_true',
                       help='Включить резюме в начало каждой главы')
    parser.add_argument('--title', type=str, default='Покрывая Небеса',
                       help='Название книги')
    parser.add_argument('--author', type=str, default='Чэнь Дун',
                       help='Автор книги')
    parser.add_argument('--only-edited', action='store_true',
                       help='Включить только отредактированные главы')
    parser.add_argument('--only-translated', action='store_true',
                       help='Использовать только переводы без редактуры')

    args = parser.parse_args()

    print("=" * 70)
    print(" ГЕНЕРАТОР EPUB (С РЕДАКТИРОВАННЫМИ ГЛАВАМИ)")
    print("=" * 70)

    # Конфигурация
    config = EPUBConfig(
        book_title=args.title,
        book_author=args.author,
        include_glossary=not args.no_glossary,
        include_summaries=args.include_summaries
    )

    print(f"\n⚙️  Конфигурация:")
    print(f"   Название: {config.book_title}")
    print(f"   Автор: {config.book_author}")
    print(f"   Включить глоссарий: {'Да' if config.include_glossary else 'Нет'}")
    print(f"   Включить резюме: {'Да' if config.include_summaries else 'Нет'}")

    if args.only_edited:
        print(f"    Режим: только отредактированные главы")
    elif args.only_translated:
        print(f"    Режим: только переводы без редактуры")
    else:
        print(f"    Режим: лучшая доступная версия каждой главы")

    # Инициализация
    db = DatabaseManager()
    generator = EPUBGenerator(config)

    # Получаем главы с учётом редактирования
    chapters = generator.get_edited_chapters_from_db(db.db_path, args.chapters)

    if not chapters:
        print("\n❌ Не найдено глав для создания EPUB!")
        db.close()
        return

    # Фильтруем по режиму
    if args.only_edited:
        chapters = [ch for ch in chapters if ch['is_edited']]
        if not chapters:
            print("\n❌ Не найдено отредактированных глав!")
            db.close()
            return
        print(f"\n Отфильтровано: {len(chapters)} отредактированных глав")
    elif args.only_translated:
        # Для режима only_translated нужно перезагрузить данные без edited_text
        # Это требует изменения запроса, пока просто предупредим
        print("\n⚠️  Режим --only-translated требует отдельной реализации")
        print("   Используются лучшие доступные версии")

    print(f"\n Подготовка к созданию EPUB с {len(chapters)} главами")

    # Получаем глоссарий если нужно
    glossary = None
    if config.include_glossary:
        glossary = db.get_glossary()
        total_terms = sum(len(cat) for cat in glossary.values())
        if total_terms > 0:
            print(f"\n Глоссарий:")
            print(f"   Персонажей: {len(glossary['characters'])}")
            print(f"   Локаций: {len(glossary['locations'])}")
            print(f"   Терминов: {len(glossary['terms'])}")

    # Создаём EPUB
    print(f"\n⏳ Создание EPUB...")
    try:
        epub_path = generator.create_epub(chapters, glossary)

        # Информация о файле
        epub_file = Path(epub_path)
        if epub_file.exists():
            size_kb = epub_file.stat().st_size / 1024

            print(f"\n✅ EPUB создан успешно!")
            print(f" Файл: {epub_path}")
            print(f" Размер: {size_kb:.1f} KB")
            print(f"\n Содержимое:")
            print(f"   - Глав всего: {len(chapters)}")
            edited_count = sum(1 for ch in chapters if ch['is_edited'])
            print(f"   - С редактурой: {edited_count}")
            print(f"   - Без редактуры: {len(chapters) - edited_count}")

            if config.include_glossary and glossary:
                print(f"   - Глоссарий с {total_terms} терминами")
            print(f"   - Оглавление с навигацией")
            print(f"   - Титульная страница")

            if edited_count > 0:
                print(f"   - Страница с информацией о редактировании")

    except Exception as e:
        print(f"\n❌ Ошибка при создании EPUB: {e}")

    db.close()


if __name__ == "__main__":
    main()