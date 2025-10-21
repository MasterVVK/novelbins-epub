#!/usr/bin/env python3
"""
Попытка получить cf_clearance через undetected-chromedriver
"""
import undetected_chromedriver as uc
import time

def test_get_cf_clearance():
    driver = None
    try:
        print("=" * 70)
        print("🧪 ТЕСТ: Получение cf_clearance через undetected-chromedriver")
        print("=" * 70)
        print()

        print("1️⃣ Создаем non-headless браузер...")
        options = uc.ChromeOptions()
        # Non-headless для лучшего обхода
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        driver = uc.Chrome(options=options, headless=False)
        print("   ✅ Браузер создан")
        print()

        print("2️⃣ Открываем czbooks.net...")
        driver.get("https://czbooks.net/n/ul6pe")
        print("   ✅ Страница открыта")
        print()

        print("3️⃣ Ждем 30 секунд для прохождения challenge...")
        for i in range(30, 0, -1):
            print(f"   ⏳ {i} сек...", end='\r', flush=True)
            time.sleep(1)
        print()
        print("   ✅ Ожидание завершено")
        print()

        print("4️⃣ Проверяем title страницы...")
        title = driver.title
        print(f"   Title: {title}")

        if "Just a moment" in title:
            print("   ⚠️ Все еще на странице challenge")
        elif "Forty Millenniums" in title or "修真四万年" in title:
            print("   ✅ Challenge пройден! Страница новеллы загружена!")
        print()

        print("5️⃣ Получаем cookies...")
        cookies = driver.get_cookies()
        print(f"   Всего cookies: {len(cookies)}")
        print()

        # Ищем Cloudflare cookies
        cf_cookies = {}
        for cookie in cookies:
            name = cookie['name']
            if name == 'cf_clearance':
                cf_cookies['cf_clearance'] = cookie['value']
                print(f"   ✅✅✅ НАЙДЕН cf_clearance: {cookie['value'][:50]}...")
            elif name == '__cf_bm':
                cf_cookies['__cf_bm'] = cookie['value']
                print(f"   ✅ НАЙДЕН __cf_bm: {cookie['value'][:30]}...")
            elif name == '_cfuvid':
                cf_cookies['_cfuvid'] = cookie['value']
                print(f"   ✅ НАЙДЕН _cfuvid: {cookie['value'][:30]}...")

        print()

        if cf_cookies.get('cf_clearance'):
            print("=" * 70)
            print("🎉🎉🎉 УСПЕХ! 🎉🎉🎉")
            print("=" * 70)
            print("cf_clearance получен!")
            print()
            print("Полный cookie string:")
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            print(cookie_string)
            print()
            print(f"Длина: {len(cookie_string)} символов")

            # Сохраняем в файл
            with open('cf_clearance_cookies.txt', 'w') as f:
                f.write(cookie_string)
            print()
            print("Сохранено в: cf_clearance_cookies.txt")

            return True
        else:
            print("=" * 70)
            print("❌ НЕУДАЧА")
            print("=" * 70)
            print("cf_clearance НЕ получен")
            print()
            print("Возможные причины:")
            print("  - Challenge требует ручного взаимодействия")
            print("  - Нужно больше времени ожидания")
            print("  - Cloudflare детектирует автоматизацию")
            print("  - Требуется прокси с другим IP")

            return False

    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if driver:
            print()
            print("Закрываем браузер через 5 секунд...")
            time.sleep(5)
            driver.quit()

if __name__ == "__main__":
    import sys
    success = test_get_cf_clearance()
    sys.exit(0 if success else 1)
