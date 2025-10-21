#!/usr/bin/env python3
"""
Тест получения cookies с czbooks.net через undetected-chromedriver
"""
import undetected_chromedriver as uc
import time
import sys

def test_cookies():
    driver = None
    try:
        print("=" * 60)
        print("ТЕСТ: Получение cookies с czbooks.net")
        print("=" * 60)

        print("\n1️⃣ Создаем undetected-chromedriver...")
        options = uc.ChromeOptions()
        # Не используем headless - видимый браузер
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        driver = uc.Chrome(options=options, headless=False)
        print("✅ Браузер создан")

        print("\n2️⃣ Открываем czbooks.net/n/ul6pe...")
        driver.get("https://czbooks.net/n/ul6pe")
        print("✅ Страница загружена")

        print("\n3️⃣ Ждем 15 секунд (для Cloudflare challenge)...")
        for i in range(15, 0, -1):
            print(f"   {i} сек...", end='\r')
            time.sleep(1)
        print("\n✅ Ожидание завершено")

        print("\n4️⃣ Получаем cookies...")
        cookies = driver.get_cookies()
        print(f"✅ Получено cookies: {len(cookies)}")

        print("\n📋 Список всех cookies:")
        print("-" * 60)
        for cookie in cookies:
            value_preview = cookie['value'][:40] + "..." if len(cookie['value']) > 40 else cookie['value']
            print(f"  • {cookie['name']}: {value_preview}")

        print("\n" + "=" * 60)
        print("🔍 CLOUDFLARE COOKIES:")
        print("=" * 60)
        cf_cookies = [c for c in cookies if 'cf' in c['name'].lower() or c['name'].startswith('__cf')]

        if cf_cookies:
            print(f"Найдено Cloudflare cookies: {len(cf_cookies)}")
            for c in cf_cookies:
                print(f"  ✅ {c['name']}: {c['value'][:50]}...")
        else:
            print("❌ Cloudflare cookies НЕ НАЙДЕНЫ!")
            print("   Ожидаемые: cf_clearance, __cf_bm, _cfuvid")

        # Проверяем конкретные cookies
        print("\n" + "=" * 60)
        print("📊 ПРОВЕРКА КЛЮЧЕВЫХ COOKIES:")
        print("=" * 60)

        cf_clearance = next((c for c in cookies if c['name'] == 'cf_clearance'), None)
        cf_bm = next((c for c in cookies if c['name'] == '__cf_bm'), None)
        cfuvid = next((c for c in cookies if c['name'] == '_cfuvid'), None)

        print(f"cf_clearance: {'✅ ЕСТЬ' if cf_clearance else '❌ НЕТ'}")
        print(f"__cf_bm:      {'✅ ЕСТЬ' if cf_bm else '❌ НЕТ'}")
        print(f"_cfuvid:      {'✅ ЕСТЬ' if cfuvid else '❌ НЕТ'}")

        # Формируем cookie string
        print("\n" + "=" * 60)
        print("📝 COOKIE STRING:")
        print("=" * 60)
        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        print(f"Длина: {len(cookie_string)} символов")
        print(f"Первые 200 символов:\n{cookie_string[:200]}...")

        # Проверяем title страницы
        print("\n" + "=" * 60)
        print("📄 ИНФОРМАЦИЯ О СТРАНИЦЕ:")
        print("=" * 60)
        print(f"Title: {driver.title}")
        print(f"URL: {driver.current_url}")

        # Итоговый результат
        print("\n" + "=" * 60)
        print("🎯 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
        print("=" * 60)

        if cf_clearance:
            print("✅✅✅ ОТЛИЧНО! ✅✅✅")
            print("cf_clearance найден - парсер должен работать!")
            print(f"\nCookie string для использования:\n{cookie_string}")
            return True
        else:
            print("❌❌❌ ПРОБЛЕМА! ❌❌❌")
            print("cf_clearance НЕ найден!")
            print("\nВозможные причины:")
            print("  1. Cloudflare challenge не показался")
            print("  2. Сайт не использует Cloudflare для этого IP")
            print("  3. Нужно подождать дольше")
            print("\nРекомендации:")
            print("  - Попробуйте с VPN")
            print("  - Или используйте другой IP")
            return False

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if driver:
            print("\n" + "=" * 60)
            print("Закрываем браузер через 5 секунд...")
            time.sleep(5)
            driver.quit()
            print("✅ Браузер закрыт")

if __name__ == "__main__":
    success = test_cookies()
    sys.exit(0 if success else 1)
