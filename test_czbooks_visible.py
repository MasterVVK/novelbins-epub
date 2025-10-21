#!/usr/bin/env python3
import undetected_chromedriver as uc
import time

driver = None
try:
    print("Открываем ВИДИМЫЙ браузер...")
    driver = uc.Chrome(headless=False)

    print("Загружаем czbooks.net...")
    driver.get("https://czbooks.net/n/ul6pe")

    print("Ждем 20 секунд...")
    time.sleep(20)

    cookies = driver.get_cookies()
    print(f"\nПолучено cookies: {len(cookies)}")

    for c in cookies:
        print(f"  {c['name']}: {c['value'][:40]}...")

    cf = [c for c in cookies if 'cf' in c['name'].lower()]
    print(f"\nCloudflare cookies: {len(cf)}")

    # Сохраняем
    cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    with open('cookies_visible.txt', 'w') as f:
        f.write(cookie_string)

    print(f"\nСохранено в cookies_visible.txt ({len(cookie_string)} символов)")

except Exception as e:
    print(f"Ошибка: {e}")
finally:
    if driver:
        time.sleep(3)
        driver.quit()
