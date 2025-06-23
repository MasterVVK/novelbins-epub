"""
3_epub_generator.py - Генерация EPUB из переведённых глав
"""
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from ebooklib import epub

from models import Chapter, EPUBConfig
from database import DatabaseManager


class EPUBGenerator:
    """Генератор EPUB файлов"""

    def __init__(self, config: EPUBConfig):
        self.config = config

    def create_epub(self, chapters: List[Chapter], glossary: dict = None) -> str:
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
            'Перевод романа "Shrouding the Heavens" (遮天). '
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

        # Создаём оглавление
        toc_page = self._create_toc_page(chapters)
        book.add_item(toc_page)

        # Список для навигации
        toc_list = []
        spine_list = ['nav', title_page, toc_page]

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
            epub.Link('toc.xhtml', 'Оглавление', 'toc'),
            (epub.Section('Главы'), toc_list[:len(chapters)])
        ]

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

        chapters_range = f"{chapters[0].number}-{chapters[-1].number}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"shrouding_the_heavens_ch{chapters_range}_{timestamp}.epub"

        # Записываем EPUB файл
        epub.write_epub(output_path, book, {})

        return str(output_path)

    def _get_css_styles(self) -> str:
        """CSS стили для книги с исправленными разрывами страниц"""
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
            /* НЕ ставим page-break-before для h1, чтобы он оставался с номером главы */
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
        
        /* Страница с номером главы */
        .chapter-number-page {
            page-break-before: always;
            page-break-after: always;
            text-align: center;
            margin-top: 40%;
            font-size: 1.2em;
            color: #666;
        }
        
        /* Контейнер для заголовка и текста главы */
        .chapter-content {
            page-break-before: always;
        }
        
        /* Альтернативный вариант: номер главы без разрыва */
        .chapter-number-inline {
            text-align: center;
            font-size: 0.9em;
            color: #666;
            margin-bottom: 0.5em;
            page-break-before: always;
            page-break-after: avoid;
        }
        
        /* Заголовок главы сразу после номера */
        .chapter-title {
            text-align: center;
            margin-top: 0.5em;
            margin-bottom: 1em;
            font-size: 1.5em;
            font-weight: bold;
            page-break-before: avoid;
            page-break-after: avoid;
        }
        
        .first-paragraph {
            text-indent: 0;
            margin-top: 1em;
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
        
        /* Медиа-запросы для электронных книг */
        @media amzn-kf8 {
            /* Специфичные стили для Kindle */
            .chapter-number-page {
                margin-top: 45%;
            }
        }
        
        @media amzn-mobi {
            /* Для старых Kindle */
            .chapter-number-page {
                page-break-after: always;
            }
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
                <p style="margin-top: 3em; font-size: 0.8em;">{datetime.now().year}</p>
            </div>
        </body>
        </html>
        '''

        return title_page

    def _create_toc_page(self, chapters: List[Chapter]) -> epub.EpubHtml:
        """Создание страницы оглавления"""
        toc_page = epub.EpubHtml(
            title='Оглавление',
            file_name='toc.xhtml',
            lang='ru'
        )

        toc_links = []
        for chapter in chapters:
            ch_filename = f'chapter_{chapter.number:03d}.xhtml'
            toc_links.append(f'<p class="toc-link"><a href="{ch_filename}">{chapter.translated_title}</a></p>')

        toc_content = '''
        <html xmlns="http://www.w3.org/1999/xhtml">
        <head>
            <title>Оглавление</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>Оглавление</h1>
            ''' + '\n'.join(toc_links) + '''
        </body>
        </html>
        '''

        toc_page.content = toc_content
        return toc_page

    def _create_chapter_page(self, chapter: Chapter, nav_css: epub.EpubItem) -> epub.EpubHtml:
        """Создание страницы главы с правильными разрывами"""
        ch_filename = f'chapter_{chapter.number:03d}.xhtml'
        ch = epub.EpubHtml(
            title=chapter.translated_title,
            file_name=ch_filename,
            lang='ru'
        )

        # Форматируем контент главы
        paragraphs = chapter.translated_text.split('\n\n')
        formatted_paragraphs = []

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if para:
                if i == 0:
                    formatted_paragraphs.append(f'<p class="first-paragraph">{para}</p>')
                else:
                    formatted_paragraphs.append(f'<p>{para}</p>')

        # Убираем номер главы из заголовка для отображения
        display_title = chapter.translated_title.replace(f"Глава {chapter.number}: ", "")

        # ВАРИАНТ 1: Две отдельные страницы (номер главы на отдельной странице)
        if self.config.separate_chapter_number_page:
            ch_content = f'''
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
                <title>{chapter.translated_title}</title>
                <link rel="stylesheet" type="text/css" href="style/nav.css"/>
            </head>
            <body>
                <!-- Отдельная страница с номером главы -->
                <div class="chapter-number-page">
                    <p>Глава {chapter.number}</p>
                </div>
                
                <!-- Страница с заголовком и текстом -->
                <div class="chapter-content">
                    <h1 class="chapter-title">{display_title}</h1>
            '''
        else:
            # ВАРИАНТ 2: Всё на одной странице (по умолчанию)
            ch_content = f'''
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
                <title>{chapter.translated_title}</title>
                <link rel="stylesheet" type="text/css" href="style/nav.css"/>
            </head>
            <body>
                <div class="chapter-number-inline">Глава {chapter.number}</div>
                <h1 class="chapter-title">{display_title}</h1>
            '''

        # Добавляем резюме если включено
        if self.config.include_summaries and chapter.summary:
            ch_content += f'''
                <div class="summary">
                    <p><em>Резюме предыдущей главы:</em></p>
                    <p>{chapter.summary}</p>
                </div>
            '''

        # Добавляем текст главы
        ch_content += '\n'.join(formatted_paragraphs)

        # Закрываем div если использовали вариант с отдельной страницей
        if self.config.separate_chapter_number_page:
            ch_content += '\n</div>'

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
    parser = argparse.ArgumentParser(description='Генератор EPUB из переведённых глав')
    parser.add_argument('-c', '--chapters', nargs='+', type=int,
                       help='Номера глав для включения в EPUB (по умолчанию все)')
    parser.add_argument('--no-glossary', action='store_true',
                       help='Не включать глоссарий')
    parser.add_argument('--include-summaries', action='store_true',
                       help='Включить резюме в начало каждой главы')
    parser.add_argument('--separate-number-page', action='store_true',
                       help='Поместить номер главы на отдельную страницу (для e-readers)')
    parser.add_argument('--title', type=str, default='Покрывая Небеса',
                       help='Название книги')
    parser.add_argument('--author', type=str, default='Чэнь Дун',
                       help='Автор книги')

    args = parser.parse_args()

    print("=" * 70)
    print("ГЕНЕРАТОР EPUB")
    print("=" * 70)

    # Конфигурация
    config = EPUBConfig(
        book_title=args.title,
        book_author=args.author,
        include_glossary=not args.no_glossary,
        include_summaries=args.include_summaries,
        separate_chapter_number_page=args.separate_number_page
    )

    print(f"\n⚙️  Конфигурация:")
    print(f"   Название: {config.book_title}")
    print(f"   Автор: {config.book_author}")
    print(f"   Включить глоссарий: {'Да' if config.include_glossary else 'Нет'}")
    print(f"   Включить резюме: {'Да' if config.include_summaries else 'Нет'}")
    print(f"   Номер главы на отдельной странице: {'Да' if config.separate_chapter_number_page else 'Нет'}")

    # Инициализация
    db = DatabaseManager()
    generator = EPUBGenerator(config)

    # Получаем главы
    chapters = db.get_translated_chapters(args.chapters)

    if not chapters:
        print("\n❌ Не найдено переведённых глав!")
        print("   Сначала запустите переводчик: python 2_translator.py")
        db.close()
        return

    print(f"\n Найдено переведённых глав: {len(chapters)}")
    for chapter in chapters:
        print(f"   - {chapter.translated_title}")

    # Получаем глоссарий если нужно
    glossary = None
    if config.include_glossary:
        glossary = db.get_glossary()
        total_terms = sum(len(cat) for cat in glossary.values())
        if total_terms > 0:
            print(f"\n Глоссарий:")
            print(f"   Персонажей: {len(glossary['characters'])}")
            print(f"   Локаций: {len(glossary['locations'])}")
            print(f"   Терминов: {len(glossary['terms'])}")

    # Создаём EPUB
    print(f"\n Создание EPUB...")
    try:
        epub_path = generator.create_epub(chapters, glossary)

        # Информация о файле
        epub_file = Path(epub_path)
        if epub_file.exists():
            size_kb = epub_file.stat().st_size / 1024

            print(f"\n✅ EPUB создан успешно!")
            print(f" Файл: {epub_path}")
            print(f" Размер: {size_kb:.1f} KB")
            print(f" Содержит:")
            print(f"   - {len(chapters)} глав")
            if config.include_glossary and glossary:
                print(f"   - Глоссарий с {total_terms} терминами")
            print(f"   - Оглавление с навигацией")
            print(f"   - Титульную страницу")

            if config.separate_chapter_number_page:
                print(f"\n ℹ️  Номера глав размещены на отдельных страницах")
                print(f"    (оптимизировано для электронных книг)")

    except Exception as e:
        print(f"\n❌ Ошибка при создании EPUB: {e}")

    db.close()


if __name__ == "__main__":
    main()