#!/usr/bin/env python3
"""
Тест парсинга czbooks.net с non-headless режимом
"""
import sys
sys.path.insert(0, '.')

from parsers import create_parser_from_url

def test_czbooks_parsing():
    """Тестируем парсинг czbooks.net"""
    print("=" * 70)
    print("🧪 ТЕСТ ПАРСИНГА CZBOOKS.NET")
    print("=" * 70)

    url = "https://czbooks.net/n/ul6pe"
    cookies = "AviviD_ios_uuid=c674dabf-8a10-4ba3-a0f4-87e74633d195; AviviD_uuid=c674dabf-8a10-4ba3-a0f4-87e74633d195; webuserid=25545b2d-39ba-ebf8-8eb0-4ad882189bea; ch_tracking_uuid=1; AviviD_session_id=1760357347"

    print(f"📍 URL: {url}")
    print(f"🍪 Cookies: {len(cookies)} символов")
    print(f"🔍 Режим: headless=False (default)")
    print()

    try:
        print("1️⃣ Создаем парсер...")
        parser = create_parser_from_url(url, auth_cookies=cookies)
        print(f"   ✅ Парсер: {parser.__class__.__name__}")
        print(f"   📚 Источник: {parser.source_name}")
        print(f"   🖥️ Headless: {parser.headless}")
        print()

        print("2️⃣ Получаем список глав...")
        chapters = parser.get_chapter_list(url)

        if not chapters:
            print("   ❌ Главы не найдены!")
            return False

        print(f"   ✅ Найдено глав: {len(chapters)}")
        print()

        # Показываем первые 3 главы
        print("📖 Первые 3 главы:")
        for i, chapter in enumerate(chapters[:3], 1):
            print(f"   {i}. {chapter['title']}")
            print(f"      URL: {chapter['url']}")
        print()

        # Пробуем загрузить первую главу
        print("3️⃣ Загружаем содержимое первой главы...")
        first_chapter = chapters[0]
        content_data = parser.get_chapter_content(first_chapter['url'])

        if not content_data or not content_data.get('content'):
            print("   ❌ Не удалось загрузить содержимое!")
            return False

        content = content_data['content']
        is_locked = content_data.get('is_locked', False)

        print(f"   ✅ Загружено: {len(content)} символов")
        print(f"   🔒 Заблокирована: {is_locked}")
        print(f"   📝 Первые 200 символов:")
        print(f"   {content[:200]}...")
        print()

        # Закрываем парсер
        parser.close()

        print("=" * 70)
        print("✅✅✅ ТЕСТ УСПЕШЕН! ✅✅✅")
        print("=" * 70)
        print(f"📊 Результат:")
        print(f"   • Найдено глав: {len(chapters)}")
        print(f"   • Первая глава загружена: {len(content)} символов")
        print(f"   • 403 ошибка: НЕТ")
        print(f"   • Non-headless режим работает!")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_czbooks_parsing()
    sys.exit(0 if success else 1)
