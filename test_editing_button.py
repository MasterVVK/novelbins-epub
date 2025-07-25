#!/usr/bin/env python3

import requests
import time

def test_editing_button():
    """Тестируем кнопку редактуры через веб-интерфейс"""
    base_url = "http://192.168.0.58:5001"
    
    print("🔍 Тестируем кнопку редактуры...")
    
    # Проверяем доступность сервера
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"✅ Сервер доступен: {response.status_code}")
    except Exception as e:
        print(f"❌ Сервер недоступен: {e}")
        return
    
    # Отправляем POST запрос на редактуру
    novel_id = 2  # ID новеллы "Покрывая Небеса"
    editing_url = f"{base_url}/novels/{novel_id}/start-editing"
    
    print(f"🚀 Отправляем запрос на редактуру: {editing_url}")
    
    try:
        response = requests.post(editing_url, timeout=30)
        print(f"📊 Ответ сервера: {response.status_code}")
        print(f"📄 Заголовки: {dict(response.headers)}")
        
        if response.status_code == 302:  # Редирект
            print(f"🔄 Редирект на: {response.headers.get('Location', 'Неизвестно')}")
        elif response.status_code == 200:
            print("✅ Запрос успешен")
        else:
            print(f"❌ Неожиданный статус: {response.status_code}")
            print(f"📄 Содержимое: {response.text[:500]}...")
            
    except Exception as e:
        print(f"❌ Ошибка при отправке запроса: {e}")
    
    # Ждем немного и проверяем задачи
    print("\n⏳ Ждем 5 секунд...")
    time.sleep(5)
    
    try:
        tasks_response = requests.get(f"{base_url}/tasks", timeout=5)
        if tasks_response.status_code == 200:
            print("✅ Страница задач доступна")
            if "editing" in tasks_response.text.lower():
                print("✅ Задача редактуры найдена в списке")
            else:
                print("❌ Задача редактуры не найдена в списке")
        else:
            print(f"❌ Не удалось получить страницу задач: {tasks_response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка при проверке задач: {e}")

if __name__ == "__main__":
    test_editing_button() 