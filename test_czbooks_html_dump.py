#!/usr/bin/env python3
"""
Дамп HTML страницы czbooks.net для анализа селекторов
"""
import sys
sys.path.insert(0, '.')

from parsers import create_parser_from_url

def dump_html():
    """Дампим HTML для анализа"""
    url = "https://czbooks.net/n/ul6pe"
    cookies = "AviviD_ios_uuid=c674dabf-8a10-4ba3-a0f4-87e74633d195; AviviD_uuid=c674dabf-8a10-4ba3-a0f4-87e74633d195; webuserid=25545b2d-39ba-ebf8-8eb0-4ad882189bea; ch_tracking_uuid=1; AviviD_session_id=1760357347"

    print("Создаем парсер...")
    parser = create_parser_from_url(url, auth_cookies=cookies, headless=False)

    print("Получаем HTML...")
    # Используем внутренний метод для получения HTML
    html = parser._get_page_with_selenium(url, wait_selector="body")

    print(f"Получено HTML: {len(html)} символов")

    # Сохраняем в файл
    with open('czbooks_page.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print("Сохранено в: czbooks_page.html")

    # Показываем первые 2000 символов
    print("\nПервые 2000 символов:")
    print("=" * 70)
    print(html[:2000])
    print("=" * 70)

    parser.close()

if __name__ == "__main__":
    dump_html()
