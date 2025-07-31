#!/usr/bin/env python3
"""
Помощник для получения cookies Qidian вручную
"""
import json

def create_cookie_template():
    """Создает шаблон для ввода cookies"""
    print("🍪 Помощник для настройки cookies Qidian")
    print("=" * 60)
    print()
    print("📋 ИНСТРУКЦИЯ:")
    print("1. Откройте браузер и войдите на https://www.qidian.com")
    print("2. Нажмите F12 (Инструменты разработчика)")
    print("3. Перейдите на вкладку 'Application' или 'Хранилище'")
    print("4. Найдите 'Cookies' → 'https://www.qidian.com'")
    print("5. Найдите и скопируйте значения следующих cookies:")
    print()
    
    # Основные cookies, которые нужны для Qidian
    required_cookies = [
        'kf_uid',           # ID пользователя
        'kf_token',         # Токен авторизации
        '_csrfToken',       # CSRF токен
        'QDuid',            # Qidian User ID
        'QDpassport',       # Паспорт пользователя
    ]
    
    optional_cookies = [
        'QDloginUserType',  # Тип пользователя
        'QDbookshelf',      # Книжная полка
        'newstatisticUUID', # Статистика
    ]
    
    cookies_dict = {}
    
    print("🔐 ОБЯЗАТЕЛЬНЫЕ COOKIES:")
    for cookie_name in required_cookies:
        print(f"\n{cookie_name}:")
        value = input(f"Введите значение для {cookie_name} (или Enter для пропуска): ").strip()
        if value:
            cookies_dict[cookie_name] = value
            print(f"✅ {cookie_name} добавлен")
        else:
            print(f"⚠️ {cookie_name} пропущен")
    
    print(f"\n📎 ДОПОЛНИТЕЛЬНЫЕ COOKIES (необязательно):")
    for cookie_name in optional_cookies:
        value = input(f"Введите значение для {cookie_name} (или Enter для пропуска): ").strip()
        if value:
            cookies_dict[cookie_name] = value
            print(f"✅ {cookie_name} добавлен")
    
    # Сохраняем cookies
    if cookies_dict:
        with open('qidian_cookies.json', 'w', encoding='utf-8') as f:
            json.dump(cookies_dict, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Cookies сохранены в qidian_cookies.json")
        print(f"📊 Сохранено cookies: {len(cookies_dict)}")
        print("\n✅ Теперь можно запускать test_qidian_api.py")
        
        return True
    else:
        print("\n⚠️ Не было введено ни одного cookie")
        return False

def show_browser_guide():
    """Показывает подробную инструкцию для разных браузеров"""
    print("\n📖 ПОДРОБНАЯ ИНСТРУКЦИЯ ПО БРАУЗЕРАМ:")
    print("=" * 60)
    
    print("\n🔵 GOOGLE CHROME:")
    print("1. Откройте https://www.qidian.com и авторизуйтесь")
    print("2. Нажмите F12")
    print("3. Вкладка 'Application' → 'Storage' → 'Cookies' → 'https://www.qidian.com'")
    print("4. Найдите нужные cookies в списке")
    print("5. Дважды кликните на 'Value' чтобы скопировать")
    
    print("\n🦊 MOZILLA FIREFOX:")
    print("1. Откройте https://www.qidian.com и авторизуйтесь")
    print("2. Нажмите F12")
    print("3. Вкладка 'Хранилище' → 'Куки' → 'https://www.qidian.com'")
    print("4. Найдите нужные cookies")
    print("5. Скопируйте значения")
    
    print("\n🌊 MICROSOFT EDGE:")
    print("1. Откройте https://www.qidian.com и авторизуйтесь")
    print("2. Нажмите F12")
    print("3. Вкладка 'Application' → 'Cookies' → 'https://www.qidian.com'")
    print("4. Найдите нужные cookies")
    print("5. Скопируйте значения")

def verify_cookies():
    """Проверяет сохраненные cookies"""
    try:
        with open('qidian_cookies.json', 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        print("\n🔍 ПРОВЕРКА СОХРАНЕННЫХ COOKIES:")
        print("=" * 60)
        
        if not cookies:
            print("❌ Файл cookies пуст")
            return False
        
        required_cookies = ['kf_uid', 'kf_token', '_csrfToken', 'QDuid']
        found_cookies = []
        missing_cookies = []
        
        for cookie_name in required_cookies:
            if cookie_name in cookies and cookies[cookie_name]:
                found_cookies.append(cookie_name)
                # Показываем только первые и последние символы для безопасности
                value = cookies[cookie_name]
                masked_value = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
                print(f"✅ {cookie_name}: {masked_value}")
            else:
                missing_cookies.append(cookie_name)
                print(f"❌ {cookie_name}: отсутствует")
        
        print(f"\n📊 Статистика:")
        print(f"   Найдено: {len(found_cookies)}/{len(required_cookies)} обязательных cookies")
        print(f"   Всего cookies: {len(cookies)}")
        
        if len(found_cookies) >= 2:  # Хотя бы 2 основных cookie
            print("\n✅ Достаточно cookies для тестирования")
            return True
        else:
            print("\n⚠️ Недостаточно cookies. Рекомендуется добавить:")
            for cookie in missing_cookies:
                print(f"   - {cookie}")
            return False
            
    except FileNotFoundError:
        print("❌ Файл qidian_cookies.json не найден")
        return False
    except Exception as e:
        print(f"❌ Ошибка при проверке cookies: {e}")
        return False

def main():
    """Главное меню"""
    print("🚀 Qidian Cookie Helper")
    print("=" * 60)
    print()
    print("Выберите действие:")
    print("1. Настроить cookies вручную")
    print("2. Показать инструкцию по браузерам")
    print("3. Проверить сохраненные cookies")
    print("4. Выход")
    
    while True:
        choice = input("\nВаш выбор (1-4): ").strip()
        
        if choice == '1':
            create_cookie_template()
            break
        elif choice == '2':
            show_browser_guide()
        elif choice == '3':
            verify_cookies()
        elif choice == '4':
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор. Введите число от 1 до 4.")

if __name__ == "__main__":
    main()