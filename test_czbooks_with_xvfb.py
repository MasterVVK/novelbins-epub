#!/usr/bin/env python3
"""
Тест парсинга czbooks.net через xvfb (виртуальный X-сервер)
ЗАПУСКАТЬ: xvfb-run python3 test_czbooks_with_xvfb.py
"""
import sys
sys.path.insert(0, '.')

from parsers import create_parser_from_url

def test_czbooks_with_xvfb():
    """Тестируем парсинг с xvfb"""
    print("=" * 70)
    print("🧪 ТЕСТ: CZBooks через Xvfb (non-headless в виртуальном дисплее)")
    print("=" * 70)

    url = "https://czbooks.net/n/ul6pe"
    # Cookies из БД (novel ID 11)
    cookies = "AviviD_ios_uuid=c674dabf-8a10-4ba3-a0f4-87e74633d195; AviviD_uuid=c674dabf-8a10-4ba3-a0f4-87e74633d195; webuserid=25545b2d-39ba-ebf8-8eb0-4ad882189bea; ch_tracking_uuid=1; AviviD_session_id=1760357347"

    print(f"📍 URL: {url}")
    print(f"🍪 Cookies: {len(cookies)} символов")
    print(f"🖥️ Режим: non-headless через Xvfb")
    print()

    try:
        print("1️⃣ Создаем парсер (headless=False)...")
        parser = create_parser_from_url(url, auth_cookies=cookies, headless=False)
        print(f"   ✅ Парсер: {parser.__class__.__name__}")
        print(f"   🖥️ Headless: {parser.headless}")
        print()

        print("2️⃣ Получаем список глав (может занять ~20 сек)...")
        chapters = parser.get_chapter_list(url)

        if not chapters:
            print("   ❌ Главы не найдены!")
            parser.close()
            return False

        print(f"   ✅ Найдено глав: {len(chapters)}")
        print()

        # Показываем первые 5 глав
        print("📖 Первые 5 глав:")
        for i, chapter in enumerate(chapters[:5], 1):
            print(f"   {i}. {chapter['title']}")
        print()

        # Пробуем загрузить первую главу
        print("3️⃣ Загружаем содержимое первой главы...")
        first_chapter = chapters[0]
        content_data = parser.get_chapter_content(first_chapter['url'])

        if not content_data or not content_data.get('content'):
            print("   ❌ Не удалось загрузить содержимое!")
            parser.close()
            return False

        content = content_data['content']
        print(f"   ✅ Загружено: {len(content)} символов")
        print(f"   📝 Первые 300 символов:")
        print(f"   {content[:300]}...")
        print()

        # Закрываем парсер
        parser.close()

        print("=" * 70)
        print("🎉🎉🎉 ИДЕАЛЬНО! 🎉🎉🎉")
        print("=" * 70)
        print(f"📊 Результат:")
        print(f"   ✅ Найдено глав: {len(chapters)}")
        print(f"   ✅ Первая глава загружена: {len(content)} символов")
        print(f"   ✅ Non-headless через Xvfb РАБОТАЕТ!")
        print(f"   ✅ Проблема 403 решена!")
        print(f"   ✅ czbooks.net парсинг работает!")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_czbooks_with_xvfb()
    sys.exit(0 if success else 1)
