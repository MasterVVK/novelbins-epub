#!/usr/bin/env python3
"""
Простой тест: могут ли cookies без cf_clearance дать доступ к czbooks.net
"""
import requests

cookies_string = "AviviD_ios_uuid=c674dabf-8a10-4ba3-a0f4-87e74633d195; AviviD_uuid=c674dabf-8a10-4ba3-a0f4-87e74633d195; webuserid=25545b2d-39ba-ebf8-8eb0-4ad882189bea; ch_tracking_uuid=1; AviviD_refresh_uuid_status=2; connectId={\"ttl\":86400000,\"lastUsed\":1760357460901,\"lastSynced\":1760357460901}; AviviD_is_pb=0; AviviD_max_time_no_move=0; AviviD_max_time_no_scroll=0; AviviD_max_time_no_click=0; AviviD_max_time_pageview=0; AviviD_max_time_pageview_total=0; AviviD_max_scroll_depth_page_last=0; AviviD_max_scroll_depth=0; AviviD_max_pageviews=3; AviviD_landing_count=2; AviviD_session_id=1760361142747"

url = "https://czbooks.net/n/ul6pe"

print("=" * 70)
print("🧪 ТЕСТ: Доступ к czbooks.net с текущими cookies")
print("=" * 70)
print(f"URL: {url}")
print(f"Cookies: {len(cookies_string)} символов")
print()

# Преобразуем cookie string в dict
cookies_dict = {}
for item in cookies_string.split('; '):
    if '=' in item:
        key, value = item.split('=', 1)
        cookies_dict[key] = value

print(f"Всего cookies: {len(cookies_dict)}")
print(f"Cloudflare cookies: НЕТ")
print()

# Делаем запрос
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

print("Отправляем запрос...")
try:
    response = requests.get(url, headers=headers, cookies=cookies_dict, timeout=10)

    print(f"Статус: {response.status_code}")
    print(f"Размер ответа: {len(response.text)} символов")
    print()

    # Проверяем содержимое
    if "Just a moment" in response.text or "challenge-platform" in response.text:
        print("❌ РЕЗУЛЬТАТ: Cloudflare Challenge страница")
        print("   Cookies БЕЗ cf_clearance НЕ РАБОТАЮТ")
    elif response.status_code == 403:
        print("❌ РЕЗУЛЬТАТ: 403 Forbidden")
        print("   Доступ заблокирован")
    elif response.status_code == 200:
        # Проверяем есть ли контент
        if len(response.text) > 50000:
            print("✅ РЕЗУЛЬТАТ: Страница загружена!")
            print(f"   Размер: {len(response.text)} символов")
            print("   Cookies РАБОТАЮТ без cf_clearance!")

            # Ищем название новеллы
            if "Forty Millenniums of Cultivation" in response.text or "修真四万年" in response.text:
                print("   ✅ Найдено название новеллы!")
        else:
            print("⚠️ РЕЗУЛЬТАТ: Маленький ответ")
            print(f"   Возможно редирект или ошибка")

    # Показываем первые 500 символов
    print()
    print("Первые 500 символов ответа:")
    print("-" * 70)
    print(response.text[:500])
    print("-" * 70)

except Exception as e:
    print(f"❌ ОШИБКА: {e}")
