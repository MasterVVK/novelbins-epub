#!/usr/bin/env python3
"""
Debug version of Qidian parser to analyze HTML structure
"""
import requests
from bs4 import BeautifulSoup
import json

def debug_book_info():
    """Debug book info extraction"""
    print("🔍 Debug: Book Info Extraction")
    print("=" * 50)
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    })
    
    book_id = "1209977"
    url = f"https://m.qidian.com/book/{book_id}"
    
    print(f"📞 Запрос: {url}")
    response = session.get(url, timeout=10)
    print(f"📊 Статус: {response.status_code}")
    print(f"📏 Размер: {len(response.text)} символов")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Проверяем все возможные селекторы для названия
        print("\n🔍 Поиск названия книги:")
        title_selectors = [
            'h1.detail__header-detail__title',
            'h1',
            '.detail__header-detail__title',
            '.title',
            '.book-title'
        ]
        
        for selector in title_selectors:
            elements = soup.select(selector)
            print(f"   {selector}: {len(elements)} элементов")
            for i, elem in enumerate(elements[:3]):  # Показываем первые 3
                print(f"      {i+1}: {elem.text.strip()[:50]}")
        
        # Проверяем все возможные селекторы для автора
        print("\n✍️ Поиск автора:")
        author_selectors = [
            'a.detail__header-detail__author-link',
            '.detail__header-detail__author-link',
            '.author',
            '.writer',
            'a[href*="author"]'
        ]
        
        for selector in author_selectors:
            elements = soup.select(selector)
            print(f"   {selector}: {len(elements)} элементов")
            for i, elem in enumerate(elements[:3]):
                print(f"      {i+1}: {elem.text.strip()[:50]}")
        
        # Проверяем все возможные селекторы для жанра
        print("\n🏷️ Поиск жанра:")
        genre_selectors = [
            'a.detail__header-detail__category',
            '.detail__header-detail__category',
            '.category',
            '.genre'
        ]
        
        for selector in genre_selectors:
            elements = soup.select(selector)
            print(f"   {selector}: {len(elements)} элементов")
            for i, elem in enumerate(elements[:3]):
                print(f"      {i+1}: {elem.text.strip()[:30]}")
        
        # Проверяем описание
        print("\n📝 Поиск описания:")
        desc_selectors = [
            'p.detail__summary__content',
            '.detail__summary__content',
            '.summary',
            '.description'
        ]
        
        for selector in desc_selectors:
            elements = soup.select(selector)
            print(f"   {selector}: {len(elements)} элементов")
            for i, elem in enumerate(elements[:2]):
                content = elem.text.strip()
                print(f"      {i+1}: {content[:100]}...")
        
        # Сохраняем HTML для анализа
        with open('debug_book_page.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"\n💾 HTML сохранен в debug_book_page.html")

def debug_catalog():
    """Debug catalog extraction"""
    print("\n🔍 Debug: Catalog Extraction")
    print("=" * 50)
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    })
    
    book_id = "1209977"
    catalog_url = f"https://m.qidian.com/book/{book_id}/catalog/"
    
    print(f"📞 Запрос каталога: {catalog_url}")
    response = session.get(catalog_url, timeout=10)
    print(f"📊 Статус: {response.status_code}")
    print(f"📏 Размер: {len(response.text)} символов")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем ссылки на главы разными способами
        print("\n📑 Поиск глав:")
        
        # Способ 1: по классу
        chapter_links_class = soup.find_all('a', class_='chapter-link')
        print(f"   По классу 'chapter-link': {len(chapter_links_class)} элементов")
        
        # Способ 2: по href паттерну
        import re
        chapter_links_href = soup.find_all('a', href=re.compile(r'/chapter/\d+/\d+/'))
        print(f"   По href паттерну: {len(chapter_links_href)} элементов")
        
        # Способ 3: все ссылки со словом "chapter"
        all_chapter_links = soup.find_all('a', href=re.compile(r'chapter'))
        print(f"   Все ссылки с 'chapter': {len(all_chapter_links)} элементов")
        
        # Показываем первые найденные ссылки
        links_to_show = chapter_links_class or chapter_links_href or all_chapter_links
        if links_to_show:
            print("\n📖 Первые найденные главы:")
            for i, link in enumerate(links_to_show[:5]):
                href = link.get('href', 'Нет href')
                title = link.text.strip()
                print(f"      {i+1}: {title[:40]} → {href}")
        
        # Сохраняем HTML каталога
        with open('debug_catalog_page.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"\n💾 HTML каталога сохранен в debug_catalog_page.html")
        
        # Анализируем структуру страницы
        print(f"\n🏗️ Структура страницы:")
        
        # Ищем основные контейнеры
        containers = [
            ('div', 'class', 'catalog'),
            ('div', 'class', 'chapter-list'),
            ('ul', None, None),
            ('div', 'id', 'chapter-list')
        ]
        
        for tag, attr, value in containers:
            if attr and value:
                elements = soup.find_all(tag, {attr: value})
            else:
                elements = soup.find_all(tag)
            print(f"   {tag}" + (f"[{attr}='{value}']" if attr else "") + f": {len(elements)} элементов")

if __name__ == "__main__":
    debug_book_info()
    debug_catalog()