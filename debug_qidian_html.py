#!/usr/bin/env python3
"""
Отладка HTML структуры Qidian для исправления селекторов
"""
import requests
from bs4 import BeautifulSoup

def debug_qidian_html():
    """
    Сохраняем и анализируем HTML для отладки
    """
    print("🔍 ОТЛАДКА HTML СТРУКТУРЫ QIDIAN")
    print("=" * 50)
    
    # URL проблемной книги
    book_id = "3106580"
    
    # Заголовки как в парсере
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # Создаем сессию
    session = requests.Session()
    session.headers.update(headers)
    
    # 1. Получаем страницу книги
    print(f"📖 Получение страницы книги {book_id}...")
    book_url = f"https://m.qidian.com/book/{book_id}/"
    
    try:
        response = session.get(book_url, timeout=10)
        print(f"   Статус: {response.status_code}")
        print(f"   Размер: {len(response.content):,} байт")
        
        if response.status_code == 200:
            # Сохраняем HTML
            with open(f"debug_book_{book_id}_mobile.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"   ✅ HTML сохранен в debug_book_{book_id}_mobile.html")
            
            # Анализируем структуру
            soup = BeautifulSoup(response.text, 'html.parser')
            
            print(f"\n📋 АНАЛИЗ СТРУКТУРЫ СТРАНИЦЫ КНИГИ:")
            
            # Ищем заголовок разными способами
            title_selectors = [
                '.book__title', '.book-title', 'h1.title', '.book-info__title', 
                'h1', '.title', '[class*="title"]', '.book-name', '.book__name'
            ]
            
            print("🔍 Поиск заголовка:")
            for selector in title_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"   ✅ {selector}: {len(elements)} элементов")
                    for i, elem in enumerate(elements[:3]):
                        text = elem.get_text(strip=True)[:50]
                        print(f"      {i+1}. '{text}'")
                else:
                    print(f"   ❌ {selector}: не найдено")
            
            # Ищем автора
            print(f"\n👤 Поиск автора:")
            author_selectors = [
                '.book__author', '.book-author', '.author', '.book-info__author',
                '[class*="author"]', '.writer', '.book-writer'
            ]
            
            for selector in author_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"   ✅ {selector}: {len(elements)} элементов")
                    for i, elem in enumerate(elements[:3]):
                        text = elem.get_text(strip=True)[:50]
                        print(f"      {i+1}. '{text}'")
                else:
                    print(f"   ❌ {selector}: не найдено")
            
            # Ищем все элементы с классами содержащими book
            print(f"\n📚 Элементы с 'book' в классах:")
            book_elements = soup.find_all(class_=lambda x: x and 'book' in x.lower())
            for elem in book_elements[:10]:
                classes = ' '.join(elem.get('class', []))
                text = elem.get_text(strip=True)[:30]
                print(f"   .{classes}: '{text}'")
                
        else:
            print(f"   ❌ Ошибка: статус {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 2. Получаем каталог глав
    print(f"\n📑 Получение каталога глав...")
    catalog_url = f"https://m.qidian.com/book/{book_id}/catalog"
    
    try:
        response = session.get(catalog_url, timeout=10)
        print(f"   Статус: {response.status_code}")
        print(f"   Размер: {len(response.content):,} байт")
        
        if response.status_code == 200:
            # Сохраняем HTML
            with open(f"debug_catalog_{book_id}_mobile.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"   ✅ HTML сохранен в debug_catalog_{book_id}_mobile.html")
            
            # Анализируем структуру каталога
            soup = BeautifulSoup(response.text, 'html.parser')
            
            print(f"\n📋 АНАЛИЗ КАТАЛОГА:")
            
            # Ищем ссылки на главы
            chapter_selectors = [
                'a.chapter__item', '.chapter-item a', 'a[href*="/chapter/"]',
                '.chapter a', 'a.chapter', '.catalog a', 'a[class*="chapter"]'
            ]
            
            print("🔍 Поиск ссылок на главы:")
            for selector in chapter_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"   ✅ {selector}: {len(elements)} элементов")
                    for i, elem in enumerate(elements[:5]):
                        href = elem.get('href', '')
                        text = elem.get_text(strip=True)[:50]
                        print(f"      {i+1}. '{text}' -> {href}")
                else:
                    print(f"   ❌ {selector}: не найдено")
            
            # Ищем все ссылки
            all_links = soup.find_all('a', href=True)
            chapter_links = [link for link in all_links if '/chapter/' in link.get('href', '')]
            print(f"\n📊 Всего ссылок с '/chapter/': {len(chapter_links)}")
            
            if chapter_links:
                print("📋 Первые 5 ссылок на главы:")
                for i, link in enumerate(chapter_links[:5]):
                    href = link.get('href')
                    text = link.get_text(strip=True)
                    classes = ' '.join(link.get('class', []))
                    print(f"   {i+1}. '{text}'")
                    print(f"      href: {href}")
                    print(f"      class: {classes}")
                    print()
        else:
            print(f"   ❌ Ошибка: статус {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print(f"\n🏁 Отладка завершена!")
    print(f"📁 Сохранены файлы:")
    print(f"   - debug_book_{book_id}_mobile.html")
    print(f"   - debug_catalog_{book_id}_mobile.html")

if __name__ == "__main__":
    debug_qidian_html()