#!/usr/bin/env python3
"""
Проверка главы 1276 - той, которую указал пользователь
"""
import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'parsers', 'sources'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'parsers', 'base'))

from czbooks_parser import CZBooksParser
from bs4 import BeautifulSoup

def test_specific_chapter():
    """Тест конкретной главы 1276"""

    test_url = "https://czbooks.net/n/ul6pe/ui23ko"  # Глава 1276

    print("=" * 80)
    print(f"🧪 ТЕСТ ГЛАВЫ 1276")
    print("=" * 80)
    print(f"\n📄 URL: {test_url}\n")

    from dotenv import load_dotenv
    load_dotenv()

    auth_cookies = os.getenv('CZBOOKS_COOKIES', '')
    socks_proxy = os.getenv('PROXY_URL', '').replace('socks5://', '')

    parser = CZBooksParser(
        auth_cookies=auth_cookies,
        socks_proxy=socks_proxy,
        headless=False
    )

    try:
        # Загружаем страницу
        html = parser._get_page_with_selenium(test_url, wait_time=25)
        soup = BeautifulSoup(html, 'html.parser')

        print("\n" + "=" * 80)
        print("📊 АНАЛИЗ КОНТЕНТА")
        print("=" * 80)

        # Ищем селектор .content
        content_elem = soup.select_one('.content')

        if content_elem:
            # Получаем весь текст
            full_text = content_elem.get_text(separator='\n', strip=True)

            print(f"\n✅ Найден элемент .content")
            print(f"   📏 Длина: {len(full_text)} символов")
            print(f"   📝 Строк: {len(full_text.split(chr(10)))}")

            # Проверяем на маркеры блокировки
            page_html = str(soup).lower()
            has_lock = any(word in page_html for word in ['lock', 'vip', 'subscribe', 'premium'])

            print(f"   🔒 Маркеры блокировки: {'ДА' if has_lock else 'НЕТ'}")

            # Показываем начало и конец
            print(f"\n   📄 Начало текста (первые 200 символов):")
            print(f"   {full_text[:200]}")

            print(f"\n   📄 Конец текста (последние 200 символов):")
            print(f"   {full_text[-200:]}")

            # Сравниваем с текстом пользователя
            user_text_start = "《一念永恆》第一千二百七十六章 蘇醒！"
            user_text_fragment = "肉身太古！"

            if user_text_start in full_text:
                print(f"\n   ✅ НАЙДЕН заголовок из текста пользователя!")
            else:
                print(f"\n   ❌ НЕ найден заголовок из текста пользователя")
                print(f"   Ожидалось: {user_text_start}")

            if user_text_fragment in full_text:
                print(f"   ✅ НАЙДЕН фрагмент 'плоть древности' из текста пользователя!")
            else:
                print(f"   ❌ НЕ найден фрагмент из текста пользователя")

            # Проверка на обрывание текста
            truncation_markers = ['UU看書', '手機用戶', '歡迎廣大書友']
            has_truncation = any(marker in full_text for marker in truncation_markers)

            if has_truncation:
                print(f"\n   ⚠️ ОБНАРУЖЕНЫ маркеры обрывания текста (превью)")
                print(f"   Это может быть не полный текст главы")
            else:
                print(f"\n   ✅ Маркеров обрывания НЕ обнаружено")

            # Определяем: это превью или полный текст?
            if len(full_text) < 500:
                verdict = "❌ СЛИШКОМ КОРОТКИЙ - скорее всего превью"
            elif has_truncation:
                verdict = "⚠️ ПРЕВЬЮ - обнаружены маркеры обрывания"
            elif len(full_text) > 5000:
                verdict = "✅ ПОЛНЫЙ ТЕКСТ - достаточная длина"
            else:
                verdict = "⚠️ НЕЯСНО - средняя длина, нужна проверка"

            print(f"\n" + "=" * 80)
            print(f"🎯 ВЕРДИКТ: {verdict}")
            print("=" * 80)

        else:
            print("\n❌ Элемент .content НЕ НАЙДЕН!")

            # Поиск альтернатив
            print("\n🔍 Поиск альтернативных селекторов...")
            for selector in ['.chapter', '#content', 'article', 'main']:
                elem = soup.select_one(selector)
                if elem:
                    text = elem.get_text(strip=True)
                    print(f"   ✅ {selector}: {len(text)} символов")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        parser.close()

if __name__ == "__main__":
    test_specific_chapter()
