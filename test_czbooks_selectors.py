#!/usr/bin/env python3
"""
Тест для проверки селекторов на czbooks.net
Помогает найти правильный селектор для извлечения контента глав
"""
import time
import sys
import os

# Добавляем пути
sys.path.append(os.path.join(os.path.dirname(__file__), 'parsers', 'sources'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'parsers', 'base'))

from czbooks_parser import CZBooksParser
from bs4 import BeautifulSoup

def test_chapter_selectors():
    """Тестирует различные селекторы для извлечения контента"""

    # Тестовый URL главы
    test_url = "https://czbooks.net/n/ul6pe/ukc8a"  # Глава 15

    print("=" * 80)
    print("🧪 ТЕСТ СЕЛЕКТОРОВ CZBOOKS.NET")
    print("=" * 80)
    print(f"\n📄 Тестовая глава: {test_url}\n")

    # Получаем cookies из .env
    from dotenv import load_dotenv
    load_dotenv()

    auth_cookies = os.getenv('CZBOOKS_COOKIES', '')
    socks_proxy = os.getenv('PROXY_URL', '').replace('socks5://', '')

    parser = CZBooksParser(
        auth_cookies=auth_cookies,
        socks_proxy=socks_proxy,
        headless=False  # non-headless для Cloudflare
    )

    try:
        # Загружаем страницу
        html = parser._get_page_with_selenium(test_url, wait_time=25)
        soup = BeautifulSoup(html, 'html.parser')

        print("\n" + "=" * 80)
        print("📊 АНАЛИЗ HTML СТРУКТУРЫ")
        print("=" * 80)

        # Ищем все возможные контейнеры
        selectors_to_test = [
            # Стандартные селекторы
            '.chapter-content',
            '#content',
            '.content',
            'article',
            'main',

            # Возможные варианты для czbooks
            '.chapter',
            '#chapter',
            '.text',
            '#text',
            '.chapter-text',
            '.novel-content',
            '.book-content',
            '[id*="content"]',
            '[class*="content"]',
            '[id*="chapter"]',
            '[class*="chapter"]',
            'div[id^="chapter"]',
            'div[class^="chapter"]',
        ]

        print("\n🔍 Проверка селекторов:")
        print("-" * 80)

        found_selectors = []

        for selector in selectors_to_test:
            try:
                elements = soup.select(selector)
                if elements:
                    for i, elem in enumerate(elements[:3]):  # Первые 3 элемента
                        text = elem.get_text(strip=True)
                        text_len = len(text)

                        # Проверяем количество параграфов
                        paragraphs = elem.find_all('p')

                        status = "✅" if text_len > 1000 else "⚠️" if text_len > 200 else "❌"

                        print(f"\n{status} Селектор: {selector} [элемент {i+1}/{len(elements)}]")
                        print(f"   📏 Длина текста: {text_len} символов")
                        print(f"   📝 Параграфов <p>: {len(paragraphs)}")

                        if text_len > 100:
                            print(f"   📄 Превью: {text[:200]}...")
                            found_selectors.append((selector, text_len, len(paragraphs)))

                        if text_len > 2000:
                            # Выводим больше информации для хороших кандидатов
                            print(f"   ✨ ОТЛИЧНЫЙ КАНДИДАТ!")
                            print(f"   🏷️ HTML теги в элементе:")
                            for tag in elem.find_all(recursive=False):
                                print(f"      - <{tag.name}> ({len(tag.get_text(strip=True))} символов)")
            except Exception as e:
                print(f"❌ Ошибка селектора {selector}: {e}")

        print("\n" + "=" * 80)
        print("📋 РЕЗЮМЕ")
        print("=" * 80)

        if found_selectors:
            print("\n✅ Найдены подходящие селекторы:")
            found_selectors.sort(key=lambda x: x[1], reverse=True)
            for selector, length, paragraphs in found_selectors[:5]:
                print(f"   {selector:30s} → {length:5d} символов, {paragraphs:3d} параграфов")

            # Рекомендация
            best_selector = found_selectors[0][0]
            print(f"\n🎯 РЕКОМЕНДУЕМЫЙ СЕЛЕКТОР: {best_selector}")
            print(f"   Длина контента: {found_selectors[0][1]} символов")
            print(f"   Параграфов: {found_selectors[0][2]}")
        else:
            print("\n❌ Подходящие селекторы не найдены!")
            print("\n🔍 Анализ всей страницы:")
            print(f"   Размер HTML: {len(html)} символов")
            print(f"   Всего <p> тегов на странице: {len(soup.find_all('p'))}")

            # Показываем все классы и ID на странице
            all_classes = set()
            all_ids = set()

            for tag in soup.find_all(True):
                if tag.get('class'):
                    all_classes.update(tag['class'])
                if tag.get('id'):
                    all_ids.add(tag['id'])

            print(f"\n   📋 Найдено уникальных классов: {len(all_classes)}")
            print(f"   Классы содержащие 'content' или 'chapter':")
            for cls in sorted(all_classes):
                if 'content' in cls.lower() or 'chapter' in cls.lower() or 'text' in cls.lower():
                    print(f"      .{cls}")

            print(f"\n   📋 Найдено уникальных ID: {len(all_ids)}")
            print(f"   ID содержащие 'content' или 'chapter':")
            for id_val in sorted(all_ids):
                if 'content' in id_val.lower() or 'chapter' in id_val.lower() or 'text' in id_val.lower():
                    print(f"      #{id_val}")

        print("\n" + "=" * 80)
        print("✅ ТЕСТ ЗАВЕРШЕН")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        parser.close()

if __name__ == "__main__":
    test_chapter_selectors()
