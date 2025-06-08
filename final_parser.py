import requests
from bs4 import BeautifulSoup, NavigableString
import json
import time
import os
from typing import List, Dict, Optional
import re

class FinalNovelBinsParser:
    def __init__(self):
        self.base_url = "https://novelbins.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get_page(self, url: str) -> Optional[str]:
        """Получение HTML страницы с обработкой ошибок"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Ошибка при загрузке {url}: {e}")
            return None

    def extract_chapter_number(self, url: str) -> int:
        """Извлечение номера главы из URL"""
        match = re.search(r'/chapter/(\d+)', url)
        return int(match.group(1)) if match else 0

    def parse_chapter_list(self, novel_url: str, max_chapters: int = 3) -> List[Dict[str, str]]:
        """Получение списка ссылок на главы"""
        print(f"Загрузка страницы новеллы: {novel_url}")
        html = self.get_page(novel_url)

        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        chapter_links = []

        # Используем найденный контейнер div.chapters
        chapters_container = soup.find('div', class_='chapters')

        if chapters_container:
            # Ищем все ссылки на главы
            all_links = chapters_container.find_all('a', href=lambda x: x and '/chapter/' in x)
            print(f"Найдено {len(all_links)} ссылок в контейнере div.chapters")

            # Создаем список всех глав с их номерами
            all_chapters = []
            for link in all_links:
                href = link.get('href', '')
                title = link.text.strip()
                chapter_num = self.extract_chapter_number(href)

                if chapter_num > 0:  # Исключаем невалидные номера
                    # Формирование полного URL
                    if href and not href.startswith('http'):
                        href = self.base_url + href

                    chapter_info = {
                        'url': href,
                        'title': title,
                        'number': chapter_num
                    }
                    all_chapters.append(chapter_info)

            # Сортируем по номеру главы (от меньшего к большему)
            all_chapters.sort(key=lambda x: x['number'])

            # Берем только первые max_chapters глав
            chapter_links = all_chapters[:max_chapters]

            print(f"\nВыбраны первые {len(chapter_links)} глав:")
            for chapter in chapter_links:
                print(f"  Глава {chapter['number']}: {chapter['title']}")
        else:
            print("Контейнер с главами не найден!")

        return chapter_links

    def extract_text_nodes(self, element, min_length=50) -> List[str]:
        """Извлечение текстовых узлов из элемента"""
        text_nodes = []

        for elem in element.descendants:
            # Проверяем, является ли элемент текстовым узлом
            if isinstance(elem, NavigableString):
                text = str(elem).strip()

                # Фильтруем короткие строки и навигационные элементы
                if len(text) >= min_length:
                    # Проверяем, не является ли это навигацией или системным текстом
                    lower_text = text.lower()
                    skip_words = ['next chapter', 'previous chapter', 'advertisement',
                                 'copyright', 'all rights reserved', 'views:', 'tags:']

                    if not any(skip in lower_text for skip in skip_words):
                        # Очищаем от лишних пробелов
                        text = ' '.join(text.split())
                        text_nodes.append(text)

        return text_nodes

    def parse_chapter_content(self, chapter_url: str, chapter_number: int) -> Dict[str, any]:
        """Парсинг содержимого одной главы"""
        print(f"\nЗагрузка главы {chapter_number}: {chapter_url}")
        html = self.get_page(chapter_url)

        if not html:
            return {'error': 'Failed to load chapter'}

        soup = BeautifulSoup(html, 'html.parser')
        result = {
            'url': chapter_url,
            'chapter_number': chapter_number,
            'title': '',
            'content': '',
            'paragraphs': [],
            'metadata': {}
        }

        # Извлечение заголовка главы
        # Ищем в разных местах
        chapter_title = None

        # Проверяем title страницы
        page_title = soup.find('title')
        if page_title:
            title_text = page_title.text.strip()
            # Извлекаем часть с Chapter X
            chapter_match = re.search(r'Chapter\s*\d+[:\s]*[^-|]+', title_text)
            if chapter_match:
                chapter_title = chapter_match.group(0).strip()

        # Если не нашли в title, ищем в тексте страницы
        if not chapter_title:
            # Ищем первый параграф с "Chapter X"
            for p in soup.find_all('p'):
                if p.text and re.match(r'^Chapter\s*\d+', p.text.strip()):
                    chapter_title = p.text.strip()
                    break

        if not chapter_title:
            chapter_title = f"Chapter {chapter_number}"

        result['title'] = chapter_title

        # Поиск основного контейнера с контентом
        # Основываясь на отладке, ищем div с классом page-content-wrapper или похожие
        content_containers = [
            soup.find('div', class_='page-content-wrapper'),
            soup.find('div', class_='page-content'),
            soup.find('div', class_='content-wrapper'),
            soup.find('div', class_='chapter-content')
        ]

        main_content = None
        for container in content_containers:
            if container:
                main_content = container
                break

        # Если не нашли по классам, ищем по размеру текста
        if not main_content:
            all_divs = soup.find_all('div')
            for div in all_divs:
                text_length = len(div.text.strip())
                if 5000 < text_length < 15000:  # Подходящий размер для главы
                    main_content = div
                    break

        if main_content:
            print(f"  Найден контейнер с контентом")

            # Удаление ненужных элементов
            for tag in main_content.find_all(['script', 'style', 'nav', 'button', 'form']):
                tag.decompose()

            # Удаление навигационных ссылок
            for link in main_content.find_all('a'):
                link_text = link.text.strip().lower()
                if any(word in link_text for word in ['next', 'previous', 'chapter list']):
                    link.decompose()

            # Извлечение текста
            # Метод 1: Пробуем найти параграфы в <p> тегах
            p_tags = main_content.find_all('p')
            paragraphs = []

            if p_tags and len(p_tags) > 5:  # Если есть достаточно p-тегов
                print(f"  Найдено {len(p_tags)} <p> тегов")
                for p in p_tags:
                    text = p.text.strip()
                    # Пропускаем заголовок главы и короткие строки
                    if text and len(text) > 30 and not text.startswith('Chapter'):
                        paragraphs.append(text)

            # Метод 2: Если мало параграфов, используем текстовые узлы
            if len(paragraphs) < 5:
                print(f"  Используем метод текстовых узлов")
                text_nodes = self.extract_text_nodes(main_content, min_length=80)

                if text_nodes:
                    print(f"  Найдено {len(text_nodes)} текстовых узлов")
                    # Объединяем короткие узлы в параграфы
                    current_paragraph = []

                    for node in text_nodes:
                        # Если узел длинный, это отдельный параграф
                        if len(node) > 200:
                            if current_paragraph:
                                paragraphs.append(' '.join(current_paragraph))
                                current_paragraph = []
                            paragraphs.append(node)
                        else:
                            # Короткий узел добавляем к текущему параграфу
                            current_paragraph.append(node)

                            # Если накопили достаточно текста, создаем параграф
                            if sum(len(t) for t in current_paragraph) > 300:
                                paragraphs.append(' '.join(current_paragraph))
                                current_paragraph = []

                    # Добавляем последний параграф
                    if current_paragraph:
                        paragraphs.append(' '.join(current_paragraph))

            # Финальная фильтрация параграфов
            filtered_paragraphs = []
            for para in paragraphs:
                # Убираем дубликаты и слишком короткие параграфы
                if para not in filtered_paragraphs and len(para) > 50:
                    filtered_paragraphs.append(para)

            result['paragraphs'] = filtered_paragraphs
            result['content'] = '\n\n'.join(filtered_paragraphs)

            # Метаданные
            result['metadata'] = {
                'word_count': len(result['content'].split()),
                'paragraph_count': len(filtered_paragraphs),
                'char_count': len(result['content']),
                'extraction_method': 'p_tags' if len(p_tags) > 5 else 'text_nodes'
            }

            print(f"  ✓ Извлечено параграфов: {len(filtered_paragraphs)}")
            print(f"  ✓ Всего слов: {result['metadata']['word_count']}")
        else:
            print("  ❌ Контент не найден!")
            result['error'] = 'Content not found'

        return result

    def save_chapters(self, chapters: List[Dict], output_dir: str = "parsed_chapters"):
        """Сохранение глав в файлы"""
        os.makedirs(output_dir, exist_ok=True)

        # Сохранение каждой главы отдельно
        for chapter in chapters:
            if 'error' in chapter:
                print(f"Пропуск главы {chapter.get('chapter_number', '?')} из-за ошибки: {chapter['error']}")
                continue

            chapter_num = chapter.get('chapter_number', 0)

            # Текстовый файл
            txt_filename = f"chapter_{chapter_num:03d}.txt"
            txt_path = os.path.join(output_dir, txt_filename)

            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(f"{chapter.get('title', 'Unknown Chapter')}\n")
                f.write("=" * 70 + "\n\n")
                f.write(chapter.get('content', ''))

            print(f"  ✓ Сохранено: {txt_path}")

            # JSON файл с полной информацией
            json_filename = f"chapter_{chapter_num:03d}.json"
            json_path = os.path.join(output_dir, json_filename)

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(chapter, f, ensure_ascii=False, indent=2)

        # Сохранение общего файла со всеми главами
        all_chapters_path = os.path.join(output_dir, "all_chapters.json")
        with open(all_chapters_path, 'w', encoding='utf-8') as f:
            json.dump(chapters, f, ensure_ascii=False, indent=2)

        print(f"\n✓ Все главы сохранены в: {output_dir}")

        # Создание объединенного файла
        combined_path = os.path.join(output_dir, "combined_chapters.txt")
        with open(combined_path, 'w', encoding='utf-8') as f:
            f.write("SHROUDING THE HEAVENS\n")
            f.write("=" * 70 + "\n\n")

            for chapter in chapters:
                if 'error' not in chapter:
                    f.write(f"{chapter.get('title', 'Unknown Chapter')}\n")
                    f.write("-" * 70 + "\n\n")
                    f.write(chapter.get('content', ''))
                    f.write("\n\n" + "=" * 70 + "\n\n")

        print(f"✓ Объединенный файл: {combined_path}")

    def parse_first_chapters(self, novel_url: str, num_chapters: int = 3):
        """Основной метод для парсинга первых N глав"""
        print("=" * 70)
        print(f"ПАРСИНГ ПЕРВЫХ {num_chapters} ГЛАВ")
        print("=" * 70)

        # Получение списка глав
        chapter_links = self.parse_chapter_list(novel_url, num_chapters)

        if not chapter_links:
            print("❌ Не удалось найти ссылки на главы!")
            return []

        print(f"\n✓ Найдено {len(chapter_links)} глав для парсинга")
        print("=" * 70)

        # Парсинг каждой главы
        parsed_chapters = []

        for i, chapter_info in enumerate(chapter_links):
            print(f"\nОбработка главы {i+1} из {len(chapter_links)}")
            print("-" * 50)

            # Парсинг контента
            chapter_data = self.parse_chapter_content(
                chapter_info['url'],
                chapter_info['number']
            )

            # Добавление информации из списка глав
            chapter_data['list_title'] = chapter_info['title']

            if 'error' not in chapter_data:
                parsed_chapters.append(chapter_data)
            else:
                print(f"  ❌ Ошибка: {chapter_data['error']}")

            # Задержка между запросами
            if i < len(chapter_links) - 1:
                print("  ⏳ Ожидание 2 секунды...")
                time.sleep(2)

        return parsed_chapters

def main():
    # URL новеллы
    novel_url = "https://novelbins.com/novel/shrouding-the-heavens-1150192/"

    # Создание парсера
    parser = FinalNovelBinsParser()

    # Парсинг первых 3 глав
    chapters = parser.parse_first_chapters(novel_url, num_chapters=3)

    if chapters:
        # Сохранение результатов
        parser.save_chapters(chapters)

        # Вывод итоговой статистики
        print("\n" + "=" * 70)
        print("ИТОГОВАЯ СТАТИСТИКА:")
        print("=" * 70)

        total_words = 0
        total_paragraphs = 0

        for chapter in chapters:
            print(f"\nГлава {chapter['chapter_number']}:")
            print(f"  Заголовок: {chapter.get('title', 'Unknown')}")

            if 'metadata' in chapter:
                words = chapter['metadata'].get('word_count', 0)
                paras = chapter['metadata'].get('paragraph_count', 0)
                method = chapter['metadata'].get('extraction_method', 'unknown')
                print(f"  Слов: {words:,}")
                print(f"  Параграфов: {paras}")
                print(f"  Метод извлечения: {method}")
                total_words += words
                total_paragraphs += paras

                # Показываем начало первого параграфа
                if chapter.get('paragraphs'):
                    print(f"  Начало текста: {chapter['paragraphs'][0][:100]}...")

        print(f"\nВСЕГО:")
        print(f"  ✓ Успешно обработано глав: {len(chapters)}")
        print(f"  ✓ Всего слов: {total_words:,}")
        print(f"  ✓ Всего параграфов: {total_paragraphs}")
        print(f"  ✓ Среднее слов на главу: {total_words // len(chapters):,}")
    else:
        print("\n❌ Не удалось спарсить главы!")

if __name__ == "__main__":
    main()