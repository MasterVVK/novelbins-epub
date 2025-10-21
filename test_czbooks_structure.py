#!/usr/bin/env python3
"""
Тестовый скрипт для анализа структуры czbooks.net
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

def analyze_czbooks_structure(url):
    """Анализ структуры страницы czbooks.net"""

    # Настройка Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.binary_location = '/usr/bin/chromium-browser'

    driver = None
    try:
        print(f"🌐 Загрузка страницы: {url}")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)

        # Ждем загрузки JavaScript
        print("⏳ Ожидание загрузки JavaScript...")
        time.sleep(5)

        # Получаем HTML
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        print("\n" + "="*60)
        print("📊 АНАЛИЗ СТРУКТУРЫ CZBOOKS.NET")
        print("="*60)

        # 1. Информация о книге
        print("\n1️⃣ ИНФОРМАЦИЯ О КНИГЕ:")
        print("-" * 40)

        # Заголовок
        title_selectors = ['h1', '.book-title', '.novel-title', '[class*="title"]']
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                print(f"  📖 Заголовок [{selector}]: {elem.get_text(strip=True)[:80]}")

        # Автор
        author_selectors = ['.author', '[class*="author"]', '.writer', '[rel="author"]']
        for selector in author_selectors:
            elem = soup.select_one(selector)
            if elem:
                print(f"  ✍️ Автор [{selector}]: {elem.get_text(strip=True)[:80]}")

        # Описание
        desc_selectors = ['.description', '.synopsis', '[class*="desc"]', '.intro']
        for selector in desc_selectors:
            elem = soup.select_one(selector)
            if elem:
                print(f"  📝 Описание [{selector}]: {elem.get_text(strip=True)[:80]}...")

        # 2. Список глав
        print("\n2️⃣ СПИСОК ГЛАВ:")
        print("-" * 40)

        # Ищем контейнер со списком глав
        chapter_containers = [
            '.chapter-list',
            '.chapters',
            '[class*="chapter"]',
            '#chapters',
            '.toc',
            '[class*="catalog"]'
        ]

        for selector in chapter_containers:
            container = soup.select_one(selector)
            if container:
                print(f"  📚 Контейнер глав: {selector}")
                # Ищем ссылки на главы
                chapter_links = container.find_all('a', href=True)
                print(f"  🔗 Найдено ссылок: {len(chapter_links)}")

                if chapter_links:
                    print("\n  Примеры глав:")
                    for i, link in enumerate(chapter_links[:5], 1):
                        href = link.get('href', '')
                        title = link.get_text(strip=True)
                        print(f"    {i}. {title[:50]}")
                        print(f"       URL: {href}")
                    break

        # 3. Все ссылки на главы (поиск по всей странице)
        print("\n3️⃣ ПОИСК ССЫЛОК НА ГЛАВЫ:")
        print("-" * 40)

        all_links = soup.find_all('a', href=True)
        chapter_links = []

        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # Проверяем, похоже ли это на ссылку на главу
            if any(keyword in href.lower() for keyword in ['chapter', 'ch', 'read', 'c_']):
                chapter_links.append({'href': href, 'text': text})

        print(f"  🔗 Найдено потенциальных ссылок на главы: {len(chapter_links)}")
        if chapter_links:
            print("\n  Первые 5 ссылок:")
            for i, ch in enumerate(chapter_links[:5], 1):
                print(f"    {i}. {ch['text'][:50]}")
                print(f"       {ch['href']}")

        # 4. Структура URL
        print("\n4️⃣ АНАЛИЗ URL:")
        print("-" * 40)
        print(f"  🌐 Базовый URL: {url}")

        if chapter_links:
            example_href = chapter_links[0]['href']
            print(f"  📄 Пример URL главы: {example_href}")

            # Определяем формат
            if example_href.startswith('http'):
                print(f"  ✅ Абсолютный URL")
            elif example_href.startswith('/'):
                print(f"  ✅ Относительный URL (от корня)")
            else:
                print(f"  ✅ Относительный URL (от текущей страницы)")

        # 5. JavaScript и динамическая загрузка
        print("\n5️⃣ ПРОВЕРКА JAVASCRIPT:")
        print("-" * 40)

        # Проверяем наличие кнопок "Загрузить больше"
        load_more_buttons = soup.find_all(['button', 'a'], string=lambda s: s and any(
            keyword in s.lower() for keyword in ['load more', 'показать еще', '更多', 'more']
        ))

        if load_more_buttons:
            print(f"  ⚠️ Найдены кнопки загрузки: {len(load_more_buttons)}")
            print("  💡 Возможно, требуется динамическая подгрузка глав")
        else:
            print(f"  ✅ Кнопки загрузки не найдены")
            print("  💡 Вероятно, все главы загружаются сразу")

        # Проверяем пагинацию
        pagination = soup.find_all(['a', 'button'], class_=lambda c: c and any(
            keyword in c.lower() for keyword in ['page', 'pag', 'next', 'prev']
        ))

        if pagination:
            print(f"  ⚠️ Найдена пагинация: {len(pagination)} элементов")
            print("  💡 Главы могут быть разделены на страницы")
        else:
            print(f"  ✅ Пагинация не найдена")

        # 6. Сохраняем HTML для детального анализа
        print("\n6️⃣ СОХРАНЕНИЕ HTML:")
        print("-" * 40)

        with open('/home/user/novelbins-epub/czbooks_sample.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("  💾 HTML сохранен в: czbooks_sample.html")

        # 7. Дополнительная информация
        print("\n7️⃣ ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:")
        print("-" * 40)

        # Классы контейнеров
        main_containers = soup.find_all(['main', 'article', 'section'])
        print(f"  📦 Основных контейнеров: {len(main_containers)}")

        for container in main_containers[:3]:
            classes = container.get('class', [])
            if classes:
                print(f"    - Класс: {' '.join(classes)}")

        # ID элементов
        elements_with_id = soup.find_all(id=True)
        print(f"  🆔 Элементов с ID: {len(elements_with_id)}")

        important_ids = [elem.get('id') for elem in elements_with_id if any(
            keyword in elem.get('id', '').lower()
            for keyword in ['chapter', 'book', 'novel', 'content', 'list']
        )]

        if important_ids:
            print("  📌 Важные ID:")
            for id_name in important_ids[:5]:
                print(f"    - #{id_name}")

        print("\n" + "="*60)
        print("✅ АНАЛИЗ ЗАВЕРШЕН")
        print("="*60)

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    # Тестовый URL
    test_url = "https://czbooks.net/n/ul6pe"
    analyze_czbooks_structure(test_url)
