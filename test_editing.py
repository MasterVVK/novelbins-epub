#!/usr/bin/env python3

import requests
import time

def test_editing_button():
    """Тестирование кнопки редактуры"""
    base_url = "http://192.168.0.58:5001"
    novel_id = 2
    
    print("🧪 Тестируем кнопку редактуры...")
    
    # 1. Проверяем страницу новеллы
    print(f"📖 Открываем страницу новеллы: {base_url}/novels/{novel_id}")
    response = requests.get(f"{base_url}/novels/{novel_id}")
    print(f"   Статус: {response.status_code}")
    
    if response.status_code == 200:
        print("   ✅ Страница загружена успешно")
    else:
        print("   ❌ Ошибка загрузки страницы")
        return
    
    # 2. Нажимаем кнопку редактуры
    print(f"🎯 Нажимаем кнопку редактуры: POST {base_url}/novels/{novel_id}/start-editing")
    
    try:
        response = requests.post(f"{base_url}/novels/{novel_id}/start-editing", timeout=10)
        print(f"   Статус: {response.status_code}")
        print(f"   Редирект: {response.url}")
        
        if response.status_code in [200, 302]:
            print("   ✅ Кнопка редактуры работает!")
            
            # Проверяем, что нас перенаправило обратно на страницу новеллы
            if "novels/2" in str(response.url) or "novels/2" in response.text:
                print("   ✅ Успешный редирект на страницу новеллы")
            else:
                print("   ⚠️ Неожиданный редирект")
        else:
            print("   ❌ Ошибка при нажатии кнопки редактуры")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Ошибка запроса: {e}")
    
    print("\n🎉 Тестирование завершено!")

if __name__ == "__main__":
    test_editing_button() 