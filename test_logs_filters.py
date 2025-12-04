#!/usr/bin/env python3
"""
Тестирование фильтров на странице логов
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

def test_log_filters():
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
        time.sleep(3)

        print("\n📊 Проверка начального состояния:")
        logs_count = driver.find_element(By.ID, 'logs-count')
        print(f"   Всего логов: {logs_count.text}")

        # Тест 1: Фильтр по уровню INFO
        print("\n🔍 Тест 1: Фильтр по уровню INFO")
        level_filter = Select(driver.find_element(By.ID, 'level-filter'))
        level_filter.select_by_value('INFO')

        apply_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Применить')]")
        apply_btn.click()
        time.sleep(2)

        logs_count = driver.find_element(By.ID, 'logs-count')
        print(f"   После фильтра INFO: {logs_count.text} логов")

        # Тест 2: Фильтр по уровню ERROR
        print("\n🔍 Тест 2: Фильтр по уровню ERROR")
        level_filter = Select(driver.find_element(By.ID, 'level-filter'))
        level_filter.select_by_value('ERROR')

        apply_btn.click()
        time.sleep(2)

        logs_count = driver.find_element(By.ID, 'logs-count')
        print(f"   После фильтра ERROR: {logs_count.text} логов")

        # Тест 3: Фильтр по времени (1 час)
        print("\n🔍 Тест 3: Фильтр по времени (1 час)")
        level_filter = Select(driver.find_element(By.ID, 'level-filter'))
        level_filter.select_by_value('')  # Сброс уровня

        hours_filter = Select(driver.find_element(By.ID, 'hours-filter'))
        hours_filter.select_by_value('1')

        apply_btn.click()
        time.sleep(2)

        logs_count = driver.find_element(By.ID, 'logs-count')
        print(f"   За последний час: {logs_count.text} логов")

        # Тест 4: Сброс фильтров
        print("\n🔍 Тест 4: Сброс фильтров")
        reset_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Сброс')]")
        reset_btn.click()
        time.sleep(2)

        logs_count = driver.find_element(By.ID, 'logs-count')
        print(f"   После сброса: {logs_count.text} логов")

        # Проверка JavaScript ошибок
        print("\n🔍 JavaScript ошибки:")
        logs = driver.get_log('browser')
        errors = [entry for entry in logs if entry['level'] == 'SEVERE' and 'favicon' not in entry['message']]
        if errors:
            for entry in errors:
                print(f"   ❌ [{entry['level']}] {entry['message'][:100]}")
        else:
            print("   ✅ Нет ошибок")

        print("\n✅ Тестирование завершено!")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            driver.quit()

if __name__ == '__main__':
    test_log_filters()
