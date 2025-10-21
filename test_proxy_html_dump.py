#!/usr/bin/env python3
"""
Дамп HTML через прокси для анализа
"""
import sys
sys.path.insert(0, '.')

from parsers import create_parser_from_url

url = "https://czbooks.net/n/ul6pe"
proxy = "socks5://192.168.0.61:1080"

print("Создаем парсер с прокси...")
parser = create_parser_from_url(url, socks_proxy=proxy, headless=False)

print("Получаем HTML...")
html = parser._get_page_with_selenium(url, wait_selector="body")

print(f"Получено HTML: {len(html)} символов")

# Сохраняем в файл
with open('czbooks_page_proxy.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Сохранено в: czbooks_page_proxy.html")

# Показываем первые 3000 символов
print("\nПервые 3000 символов:")
print("=" * 70)
print(html[:3000])
print("=" * 70)

# Ищем ссылки на главы
import re
chapter_links = re.findall(r'href="([^"]*chapter[^"]*)"', html, re.IGNORECASE)
print(f"\nНайдено ссылок со словом 'chapter': {len(chapter_links)}")
for i, link in enumerate(chapter_links[:10], 1):
    print(f"  {i}. {link}")

parser.close()
