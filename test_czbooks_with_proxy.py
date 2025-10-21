#!/usr/bin/env python3
"""
Тест парсинга czbooks.net через SOCKS5 прокси
"""
import sys
sys.path.insert(0, '.')

from parsers import create_parser_from_url

def test_with_proxy():
    """Тестируем парсинг через прокси"""
    print("=" * 70)
    print("🧪 ТЕСТ: CZBooks через SOCKS5 прокси")
    print("=" * 70)

    url = "https://czbooks.net/n/ul6pe"
    proxy = "socks5://192.168.0.61:1080"

    print(f"📍 URL: {url}")
    print(f"🌐 Прокси: {proxy}")
    print(f"🖥️ Режим: headless=False (через Xvfb)")
    print()

    try:
        print("1️⃣ Создаем парсер с прокси...")
        parser = create_parser_from_url(
            url,
            socks_proxy=proxy,
            headless=False  # non-headless через Xvfb
        )
        print(f"   ✅ Парсер: {parser.__class__.__name__}")
        print(f"   🖥️ Headless: {parser.headless}")
        print()

        print("2️⃣ Получаем список глав через прокси...")
        print("   (может занять ~30-60 сек для прохождения Cloudflare)")
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
            print(f"      URL: {chapter.get('url', 'N/A')}")
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
        print(f"   ✅ Прокси работает!")
        print(f"   ✅ Cloudflare challenge пройден!")
        print(f"   ✅ Найдено глав: {len(chapters)}")
        print(f"   ✅ Первая глава загружена: {len(content)} символов")
        print(f"   ✅ czbooks.net парсинг РАБОТАЕТ через прокси!")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_with_proxy()
    sys.exit(0 if success else 1)
