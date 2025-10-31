#!/usr/bin/env python3
"""
Утилита для получения cookies с czbooks.net для обхода Cloudflare Turnstile

Использование:
    python get_czbooks_cookies.py

Скрипт откроет браузер Chrome в GUI режиме.
Вам нужно:
1. Дождаться загрузки страницы czbooks.net
2. Вручную пройти Cloudflare Turnstile challenge (если появится)
3. Дождаться полной загрузки страницы
4. Нажать Enter в терминале

После этого скрипт извлечет cookies и покажет их для копирования.
"""

import sys
import os

# Убедимся, что используется правильный chromedriver путь
os.environ['PATH'] = '/usr/bin:' + os.environ.get('PATH', '')

try:
    import undetected_chromedriver as uc
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    import time
    import json
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Установите зависимости: pip install undetected-chromedriver selenium")
    sys.exit(1)

def get_cookies():
    """Получить cookies с czbooks.net"""
    print("=" * 60)
    print("Утилита получения cookies для czbooks.net")
    print("=" * 60)
    print()

    url = "https://czbooks.net"

    print("🚀 Запуск Chrome в GUI режиме...")
    print("⚠️  ВАЖНО: Этот скрипт должен запускаться на машине с GUI (не через SSH)")
    print()

    # Настройки Chrome
    options = uc.ChromeOptions()
    # НЕ используем headless - нужен GUI для прохождения Turnstile
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')

    # Инициализация драйвера
    try:
        print("🔧 Инициализация undetected-chromedriver...")
        driver = uc.Chrome(options=options, version_main=141)
        print("✅ Chrome запущен")
        print()
    except Exception as e:
        print(f"❌ Ошибка запуска Chrome: {e}")
        print()
        print("💡 Попробуйте:")
        print("   1. Запустить скрипт на машине с графическим интерфейсом")
        print("   2. Или использовать VNC/X11 forwarding для удаленного доступа")
        sys.exit(1)

    try:
        # Открываем страницу
        print(f"📄 Загрузка {url}...")
        driver.get(url)
        print("✅ Страница загружена")
        print()

        # Даем время на автоматическое прохождение challenge
        print("⏳ Ожидание автоматического прохождения Cloudflare (30 секунд)...")
        time.sleep(30)

        # Проверяем, прошли ли challenge
        page_source = driver.page_source
        if 'Verify you are human' in page_source or 'cf-chl' in page_source:
            print("⚠️  Cloudflare Turnstile активен!")
            print()
            print("ИНСТРУКЦИЯ:")
            print("1. Найдите окно Chrome, которое открыл этот скрипт")
            print("2. Пройдите Cloudflare challenge (нажмите на галочку/checkbox)")
            print("3. Дождитесь полной загрузки страницы czbooks.net")
            print("4. Вернитесь в этот терминал и нажмите Enter")
            print()
            input("Нажмите Enter после прохождения challenge... ")
        else:
            print("✅ Cloudflare challenge пройден автоматически!")
            print()

        # Получаем cookies
        cookies = driver.get_cookies()
        print(f"📦 Получено {len(cookies)} cookies")
        print()

        # Формируем строку cookies для вставки в БД
        auth_cookies = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

        print("=" * 60)
        print("✅ Cookies успешно получены!")
        print("=" * 60)
        print()
        print("Скопируйте эту строку и добавьте в настройки новеллы:")
        print()
        print(auth_cookies)
        print()
        print("=" * 60)
        print()
        print("Для добавления cookies в базу данных:")
        print()
        print("1. Откройте веб-интерфейс: http://192.168.0.58:5001/novels/13")
        print("2. Нажмите 'Редактировать'")
        print("3. Включите 'Auth Cookies Enabled'")
        print("4. Вставьте cookies в поле 'Auth Cookies'")
        print("5. Сохраните изменения")
        print()
        print("Или через SQL:")
        print(f"""
sqlite3 web_app/instance/novel_translator.db "UPDATE novels SET auth_enabled=1, auth_cookies='{auth_cookies[:50]}...' WHERE id=13"
""")

        # Сохраняем в файл для удобства
        cookies_file = '/tmp/czbooks_cookies.txt'
        with open(cookies_file, 'w') as f:
            f.write(auth_cookies)
        print(f"💾 Cookies сохранены в {cookies_file}")
        print()

    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        print("🔒 Закрытие браузера...")
        driver.quit()
        print("✅ Готово!")

if __name__ == '__main__':
    get_cookies()
