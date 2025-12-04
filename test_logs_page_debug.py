#!/usr/bin/env python3
"""
Тестовый скрипт для проверки страницы логов
Проверяет JavaScript ошибки и отображение логов
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def test_logs_page():
    # Настройка headless браузера
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)

        print("🌐 Открываем страницу логов...")
        driver.get('http://192.168.0.58:5001/logs')

        # Ждем загрузки страницы
        time.sleep(3)

        print("\n📊 Проверка элементов страницы:")

        # Проверяем наличие контейнера логов
        logs_container = driver.find_element(By.ID, 'logs-container')
        print(f"✅ Контейнер логов найден: {logs_container.tag_name}")
        print(f"   HTML контента: {logs_container.get_attribute('innerHTML')[:200]}...")

        # Проверяем счетчик логов
        try:
            logs_count = driver.find_element(By.ID, 'logs-count')
            print(f"✅ Счетчик логов: {logs_count.text}")
        except:
            print("❌ Счетчик логов не найден")

        # Проверяем статистику
        try:
            total_logs = driver.find_element(By.ID, 'total-logs')
            print(f"✅ Всего логов: {total_logs.text}")
        except:
            print("❌ Статистика логов не найдена")

        # Получаем JavaScript ошибки из консоли
        print("\n🔍 JavaScript ошибки в консоли:")
        logs = driver.get_log('browser')
        if logs:
            for entry in logs:
                print(f"   [{entry['level']}] {entry['message']}")
        else:
            print("   ✅ Нет ошибок в консоли")

        # Проверяем, что loadLogs() выполнилась
        print("\n🔧 Проверка выполнения loadLogs():")
        logs_loaded = driver.execute_script("""
            return document.querySelectorAll('.log-entry').length;
        """)
        print(f"   Найдено log-entry элементов: {logs_loaded}")

        if logs_loaded == 0:
            print("\n⚠️  ПРОБЛЕМА: Логи не отображаются!")
            print("   Проверяем запрос к API...")

            # Выполняем fetch вручную и смотрим результат
            api_result = driver.execute_script("""
                return fetch('/api/logs/recent?hours=24&limit=5')
                    .then(r => r.json())
                    .then(data => JSON.stringify(data))
                    .catch(err => 'ERROR: ' + err);
            """)
            time.sleep(2)
            print(f"   API ответ: {api_result}")
        else:
            print(f"\n✅ Логи отображаются корректно ({logs_loaded} шт.)")

        # Делаем скриншот для отладки
        driver.save_screenshot('/tmp/logs_page_debug.png')
        print("\n📸 Скриншот сохранен: /tmp/logs_page_debug.png")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            driver.quit()

if __name__ == '__main__':
    test_logs_page()
