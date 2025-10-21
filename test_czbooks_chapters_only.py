#!/usr/bin/env python3
"""
Быстрый тест - только список глав
"""
import sys
sys.path.insert(0, '.')

from parsers import create_parser_from_url

url = "https://czbooks.net/n/ul6pe"
proxy = "socks5://192.168.0.61:1080"

print("Создаем парсер...")
parser = create_parser_from_url(url, socks_proxy=proxy, headless=False)

print("Получаем список глав...")
chapters = parser.get_chapter_list(url)

print(f"\n✅ Найдено глав: {len(chapters)}")
print("\nПервые 10 глав:")
for i, ch in enumerate(chapters[:10], 1):
    print(f"  {i}. {ch['title']}")
    print(f"      URL: {ch['url']}")

parser.close()
