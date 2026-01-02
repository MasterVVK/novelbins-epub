#!/usr/bin/env python3
"""
Тест: сравнение поведения Cloudflare для разных режимов Selenium
"""
import time
import os

# Тест 1: Обычный Selenium (headless)
def test_regular_selenium():
    print("\n" + "="*60)
    print("TEST 1: Обычный Selenium (headless)")
    print("="*60)

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.binary_location = '/usr/bin/chromium-browser'

    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(60)

    try:
        print("Загрузка czbooks.net...")
        driver.get("https://czbooks.net/n/s6pcc1")
        time.sleep(10)

        page_source = driver.page_source
        page_size = len(page_source)
        chinese_chars = len([c for c in page_source if '\u4e00' <= c <= '\u9fff'])

        # Проверка индикаторов Cloudflare
        cf_indicators = {
            'Just a moment': 'Just a moment' in page_source,
            'Verify you are human': 'Verify you are human' in page_source,
            'cf-chl': 'cf-chl' in page_source,
            'turnstile': 'turnstile' in page_source.lower(),
            'challenge-platform': 'challenge-platform' in page_source,
        }

        print(f"\n📊 Результаты:")
        print(f"   Размер страницы: {page_size} символов")
        print(f"   Китайских символов: {chinese_chars}")
        print(f"\n   Индикаторы Cloudflare:")
        for name, found in cf_indicators.items():
            status = "⚠️ НАЙДЕН" if found else "✅ нет"
            print(f"      {name}: {status}")

        # Проверка реального контента
        has_content = any([
            '<div class="name"' in page_source,
            chinese_chars > 500,
        ])
        print(f"\n   Реальный контент czbooks: {'✅ ДА' if has_content else '❌ НЕТ'}")

        # Сохраняем HTML для анализа
        with open('/tmp/test_regular_selenium.html', 'w', encoding='utf-8') as f:
            f.write(page_source)
        print(f"   HTML сохранён: /tmp/test_regular_selenium.html")

        return {
            'mode': 'regular_selenium_headless',
            'page_size': page_size,
            'chinese_chars': chinese_chars,
            'cloudflare_active': any(cf_indicators.values()),
            'has_content': has_content
        }

    finally:
        driver.quit()


# Тест 2: undetected-chromedriver (headless)
def test_undetected_headless():
    print("\n" + "="*60)
    print("TEST 2: undetected-chromedriver (headless)")
    print("="*60)

    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')

    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(60)

    try:
        print("Загрузка czbooks.net...")
        driver.get("https://czbooks.net/n/s6pcc1")
        time.sleep(10)

        page_source = driver.page_source
        page_size = len(page_source)
        chinese_chars = len([c for c in page_source if '\u4e00' <= c <= '\u9fff'])

        cf_indicators = {
            'Just a moment': 'Just a moment' in page_source,
            'Verify you are human': 'Verify you are human' in page_source,
            'cf-chl': 'cf-chl' in page_source,
            'turnstile': 'turnstile' in page_source.lower(),
            'challenge-platform': 'challenge-platform' in page_source,
        }

        print(f"\n📊 Результаты:")
        print(f"   Размер страницы: {page_size} символов")
        print(f"   Китайских символов: {chinese_chars}")
        print(f"\n   Индикаторы Cloudflare:")
        for name, found in cf_indicators.items():
            status = "⚠️ НАЙДЕН" if found else "✅ нет"
            print(f"      {name}: {status}")

        has_content = any([
            '<div class="name"' in page_source,
            chinese_chars > 500,
        ])
        print(f"\n   Реальный контент czbooks: {'✅ ДА' if has_content else '❌ НЕТ'}")

        with open('/tmp/test_undetected_headless.html', 'w', encoding='utf-8') as f:
            f.write(page_source)
        print(f"   HTML сохранён: /tmp/test_undetected_headless.html")

        return {
            'mode': 'undetected_headless',
            'page_size': page_size,
            'chinese_chars': chinese_chars,
            'cloudflare_active': any(cf_indicators.values()),
            'has_content': has_content
        }

    finally:
        driver.quit()


# Тест 3: undetected-chromedriver (non-headless через Xvfb)
def test_undetected_xvfb():
    print("\n" + "="*60)
    print("TEST 3: undetected-chromedriver (non-headless, DISPLAY=" + os.environ.get('DISPLAY', 'не задан') + ")")
    print("="*60)

    if not os.environ.get('DISPLAY'):
        print("⚠️ DISPLAY не задан, пропускаем тест")
        return None

    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    # НЕ добавляем --headless
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')

    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(60)

    try:
        print("Загрузка czbooks.net...")
        driver.get("https://czbooks.net/n/s6pcc1")
        time.sleep(15)  # Больше времени для non-headless

        page_source = driver.page_source
        page_size = len(page_source)
        chinese_chars = len([c for c in page_source if '\u4e00' <= c <= '\u9fff'])

        cf_indicators = {
            'Just a moment': 'Just a moment' in page_source,
            'Verify you are human': 'Verify you are human' in page_source,
            'cf-chl': 'cf-chl' in page_source,
            'turnstile': 'turnstile' in page_source.lower(),
            'challenge-platform': 'challenge-platform' in page_source,
        }

        print(f"\n📊 Результаты:")
        print(f"   Размер страницы: {page_size} символов")
        print(f"   Китайских символов: {chinese_chars}")
        print(f"\n   Индикаторы Cloudflare:")
        for name, found in cf_indicators.items():
            status = "⚠️ НАЙДЕН" if found else "✅ нет"
            print(f"      {name}: {status}")

        has_content = any([
            '<div class="name"' in page_source,
            chinese_chars > 500,
        ])
        print(f"\n   Реальный контент czbooks: {'✅ ДА' if has_content else '❌ НЕТ'}")

        with open('/tmp/test_undetected_xvfb.html', 'w', encoding='utf-8') as f:
            f.write(page_source)
        print(f"   HTML сохранён: /tmp/test_undetected_xvfb.html")

        return {
            'mode': 'undetected_xvfb',
            'page_size': page_size,
            'chinese_chars': chinese_chars,
            'cloudflare_active': any(cf_indicators.values()),
            'has_content': has_content
        }

    finally:
        driver.quit()


if __name__ == "__main__":
    print("🔬 ТЕСТ: Сравнение поведения Cloudflare для разных режимов Selenium")
    print("=" * 60)

    results = []

    # Тест 1
    try:
        r1 = test_regular_selenium()
        results.append(r1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")

    time.sleep(3)

    # Тест 2
    try:
        r2 = test_undetected_headless()
        results.append(r2)
    except Exception as e:
        print(f"❌ Ошибка: {e}")

    time.sleep(3)

    # Тест 3
    try:
        r3 = test_undetected_xvfb()
        if r3:
            results.append(r3)
    except Exception as e:
        print(f"❌ Ошибка: {e}")

    # Итоги
    print("\n" + "="*60)
    print("📊 СВОДКА РЕЗУЛЬТАТОВ")
    print("="*60)

    for r in results:
        cf_status = "⚠️ Cloudflare АКТИВЕН" if r['cloudflare_active'] else "✅ Cloudflare НЕ активен"
        content_status = "✅ Контент есть" if r['has_content'] else "❌ Контента нет"
        print(f"\n{r['mode']}:")
        print(f"   {cf_status}")
        print(f"   {content_status}")
        print(f"   Размер: {r['page_size']}, Китайских: {r['chinese_chars']}")
