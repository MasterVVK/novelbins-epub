#!/usr/bin/env python3
"""
Тест получения cookies с czbooks.net через undetected-chromedriver (headless)
"""
import undetected_chromedriver as uc
import time
import json

def test_cookies_headless():
    driver = None
    result = {
        'success': False,
        'cookies_count': 0,
        'has_cf_clearance': False,
        'cookies': [],
        'error': None
    }

    try:
        print("Создаем headless браузер...")
        options = uc.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

        driver = uc.Chrome(options=options, headless=True)
        print("✅ Браузер создан")

        print("Открываем czbooks.net...")
        driver.get("https://czbooks.net/n/ul6pe")
        print("✅ Страница загружена")

        print("Ждем 20 секунд...")
        time.sleep(20)

        print("Получаем cookies...")
        cookies = driver.get_cookies()

        result['cookies_count'] = len(cookies)
        result['cookies'] = cookies

        # Проверяем cf_clearance
        cf_clearance = next((c for c in cookies if c['name'] == 'cf_clearance'), None)
        result['has_cf_clearance'] = cf_clearance is not None

        if cf_clearance:
            result['success'] = True

        # Сохраняем в файл
        with open('cookies_test_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Получено cookies: {len(cookies)}")
        print(f"cf_clearance: {'✅ ЕСТЬ' if cf_clearance else '❌ НЕТ'}")

        for cookie in cookies:
            print(f"  - {cookie['name']}")

        return result

    except Exception as e:
        result['error'] = str(e)
        print(f"❌ Ошибка: {e}")
        return result

    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    result = test_cookies_headless()
    print("\nРезультат сохранен в: cookies_test_result.json")
