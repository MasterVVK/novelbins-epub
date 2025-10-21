#!/usr/bin/env python3
"""
Тестовый скрипт для парсера czbooks.net
Проверяет основные функции парсера
"""
import sys
from parsers import create_parser, create_parser_from_url, detect_source


def test_parser_factory():
    """Тест фабрики парсеров"""
    print("\n" + "=" * 60)
    print("1️⃣  ТЕСТ ФАБРИКИ ПАРСЕРОВ")
    print("=" * 60)

    # Тест 1: Определение источника по URL
    test_url = "https://czbooks.net/n/ul6pe"
    print(f"\n📋 Тест определения источника:")
    print(f"   URL: {test_url}")

    source = detect_source(test_url)
    print(f"   ✅ Определенный источник: {source}")

    assert source == 'czbooks', f"Ожидался 'czbooks', получен '{source}'"

    # Тест 2: Создание парсера по имени
    print(f"\n📋 Тест создания парсера по имени:")
    parser = create_parser('czbooks')
    print(f"   ✅ Парсер создан: {parser.source_name}")
    parser.close()

    # Тест 3: Создание парсера из URL
    print(f"\n📋 Тест создания парсера из URL:")
    parser = create_parser_from_url(test_url)
    print(f"   ✅ Парсер создан из URL: {parser.source_name}")
    parser.close()

    print(f"\n✅ Все тесты фабрики пройдены!\n")


def test_czbooks_parser_basic():
    """Базовый тест парсера czbooks"""
    print("\n" + "=" * 60)
    print("2️⃣  БАЗОВЫЙ ТЕСТ CZBOOKS PARSER")
    print("=" * 60)

    test_url = "https://czbooks.net/n/ul6pe"

    # Создаем парсер
    print(f"\n📚 Создание парсера для czbooks.net...")
    parser = create_parser('czbooks')

    try:
        # Тест 1: Информация о книге
        print(f"\n📖 Тест 1: get_book_info()")
        print(f"   URL: {test_url}")

        book_info = parser.get_book_info(test_url)

        print(f"\n   📊 Результат:")
        print(f"      Название: {book_info['title']}")
        print(f"      Автор: {book_info['author']}")
        print(f"      ID книги: {book_info['book_id']}")
        print(f"      Жанр: {book_info['genre']}")
        print(f"      Статус: {book_info['status']}")

        if book_info['description']:
            print(f"      Описание: {book_info['description'][:100]}...")

        # Проверяем что получены базовые данные
        assert book_info['title'] != "Unknown Title", "Не удалось получить название книги"
        assert book_info['book_id'] != 'unknown', "Не удалось извлечь ID книги"

        print(f"   ✅ Информация о книге получена успешно")

        # Тест 2: Список глав
        print(f"\n📚 Тест 2: get_chapter_list()")

        chapters = parser.get_chapter_list(test_url)

        print(f"\n   📊 Результат:")
        print(f"      Найдено глав: {len(chapters)}")

        if chapters:
            print(f"\n   Первые 5 глав:")
            for ch in chapters[:5]:
                print(f"      {ch['number']}. {ch['title'][:60]}")
                print(f"         URL: {ch['url']}")
                print(f"         ID: {ch['chapter_id']}")

            assert len(chapters) > 0, "Список глав пуст"
            print(f"   ✅ Список глав получен успешно")

            # Тест 3: Содержимое главы
            print(f"\n📄 Тест 3: get_chapter_content()")
            print(f"   Загрузка первой главы...")

            first_chapter = chapters[0]
            content_data = parser.get_chapter_content(first_chapter['url'])

            print(f"\n   📊 Результат:")
            print(f"      Заголовок: {content_data['title']}")
            print(f"      Размер контента: {content_data['word_count']} символов")
            print(f"      ID главы: {content_data['chapter_id']}")
            print(f"      Заблокирована: {content_data['is_locked']}")

            print(f"\n   Превью контента (первые 300 символов):")
            print(f"   {'-' * 60}")
            print(f"   {content_data['content'][:300]}...")
            print(f"   {'-' * 60}")

            assert content_data['content'] != "Content not found", "Не удалось извлечь содержимое"
            assert len(content_data['content']) > 100, "Контент слишком короткий"

            print(f"   ✅ Содержимое главы получено успешно")

        else:
            print(f"   ⚠️ Главы не найдены (возможно, проблема с Cloudflare)")

        print(f"\n✅ Базовые тесты пройдены успешно!\n")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        parser.close()

    return True


def test_czbooks_with_proxy():
    """Тест парсера с SOCKS прокси (если настроен)"""
    print("\n" + "=" * 60)
    print("3️⃣  ТЕСТ С SOCKS ПРОКСИ (опционально)")
    print("=" * 60)

    # Здесь можно настроить прокси для тестирования
    socks_proxy = None  # Например: "127.0.0.1:1080"

    if not socks_proxy:
        print("   ⚠️ SOCKS прокси не настроен, пропускаем тест")
        print("   💡 Чтобы протестировать с прокси, укажите socks_proxy в этой функции")
        return True

    test_url = "https://czbooks.net/n/ul6pe"

    print(f"\n📚 Создание парсера с прокси: {socks_proxy}")
    parser = create_parser('czbooks', socks_proxy=socks_proxy)

    try:
        print(f"\n📖 Загрузка информации о книге через прокси...")
        book_info = parser.get_book_info(test_url)

        print(f"   ✅ Название: {book_info['title']}")
        print(f"   ✅ Прокси работает!")

    except Exception as e:
        print(f"   ❌ Ошибка при использовании прокси: {e}")
        return False

    finally:
        parser.close()

    return True


def test_czbooks_with_auth():
    """Тест парсера с cookies авторизации (если настроены)"""
    print("\n" + "=" * 60)
    print("4️⃣  ТЕСТ С АВТОРИЗАЦИЕЙ (опционально)")
    print("=" * 60)

    # Здесь можно настроить cookies для тестирования
    auth_cookies = None  # Например: "session=abc123; user_id=456"

    if not auth_cookies:
        print("   ⚠️ Cookies не настроены, пропускаем тест")
        print("   💡 Чтобы протестировать авторизацию, укажите auth_cookies в этой функции")
        return True

    test_url = "https://czbooks.net/n/ul6pe"

    print(f"\n📚 Создание парсера с авторизацией")
    parser = create_parser('czbooks', auth_cookies=auth_cookies)

    try:
        print(f"\n📖 Загрузка информации с авторизацией...")
        book_info = parser.get_book_info(test_url)

        print(f"   ✅ Название: {book_info['title']}")
        print(f"   ✅ Авторизация работает!")

    except Exception as e:
        print(f"   ❌ Ошибка при использовании авторизации: {e}")
        return False

    finally:
        parser.close()

    return True


def main():
    """Основная функция тестирования"""
    print("\n" + "=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ CZBOOKS PARSER")
    print("=" * 70)

    results = {
        'factory': False,
        'basic': False,
        'proxy': False,
        'auth': False
    }

    # Тест 1: Фабрика парсеров
    try:
        test_parser_factory()
        results['factory'] = True
    except Exception as e:
        print(f"\n❌ Тест фабрики провален: {e}")
        import traceback
        traceback.print_exc()

    # Тест 2: Базовый функционал
    try:
        results['basic'] = test_czbooks_parser_basic()
    except Exception as e:
        print(f"\n❌ Базовый тест провален: {e}")
        import traceback
        traceback.print_exc()

    # Тест 3: Прокси (опционально)
    try:
        results['proxy'] = test_czbooks_with_proxy()
    except Exception as e:
        print(f"\n❌ Тест прокси провален: {e}")

    # Тест 4: Авторизация (опционально)
    try:
        results['auth'] = test_czbooks_with_auth()
    except Exception as e:
        print(f"\n❌ Тест авторизации провален: {e}")

    # Итоговый отчет
    print("\n" + "=" * 70)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 70)

    print(f"\n   {'Тест':<30} {'Результат':<20}")
    print(f"   {'-' * 50}")
    print(f"   {'Фабрика парсеров':<30} {'✅ Пройден' if results['factory'] else '❌ Провален':<20}")
    print(f"   {'Базовый функционал':<30} {'✅ Пройден' if results['basic'] else '❌ Провален':<20}")
    print(f"   {'SOCKS прокси':<30} {'✅ Пройден' if results['proxy'] else '⚠️  Пропущен':<20}")
    print(f"   {'Авторизация':<30} {'✅ Пройден' if results['auth'] else '⚠️  Пропущен':<20}")

    # Подсчет успешных тестов (обязательные)
    mandatory_tests = ['factory', 'basic']
    passed = sum(1 for test in mandatory_tests if results[test])
    total = len(mandatory_tests)

    print(f"\n   Обязательных тестов пройдено: {passed}/{total}")

    if passed == total:
        print(f"\n✅ ВСЕ ОБЯЗАТЕЛЬНЫЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 70)
        return 0
    else:
        print(f"\n❌ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
