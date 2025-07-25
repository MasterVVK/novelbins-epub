#!/usr/bin/env python3
"""
Скрипт для анализа структуры сайта novelbins.com
"""
import requests
from bs4 import BeautifulSoup
import re

def analyze_novelbins_structure():
    """Анализ структуры сайта novelbins.com"""
    url = "https://novelbins.com/novel/shrouding-the-heavens-1150192/"
    
    print("🔍 Анализ структуры сайта novelbins.com")
    print("=" * 50)
    
    try:
        # Получаем страницу
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print(f"✅ Страница загружена: {response.status_code}")
        print(f"📄 Размер HTML: {len(response.text)} символов")
        
        # Ищем заголовок
        title = soup.find('title')
        if title:
            print(f"📖 Заголовок: {title.text}")
        
        # Ищем информацию о новелле
        novel_info = soup.find('h1')
        if novel_info:
            print(f"📚 Название: {novel_info.text.strip()}")
        
        # Ищем автора
        author = soup.find('p', string=re.compile(r'Author:', re.I))
        if author:
            print(f"✍️ Автор: {author.text.strip()}")
        
        # Ищем последнюю главу
        latest_chapter = soup.find('p', string=re.compile(r'Latest:', re.I))
        if latest_chapter:
            print(f"📖 Последняя глава: {latest_chapter.text.strip()}")
        
        # Ищем все ссылки на главы
        chapter_links = soup.find_all('a', href=re.compile(r'/chapter/\d+'))
        print(f"\n🔗 Найдено ссылок на главы: {len(chapter_links)}")
        
        if chapter_links:
            print("📋 Примеры ссылок на главы:")
            for i, link in enumerate(chapter_links[:5]):
                print(f"  {i+1}. {link.text.strip()} -> {link['href']}")
        
        # Ищем навигационные элементы
        nav_elements = soup.find_all(['nav', 'ul', 'div'], class_=re.compile(r'nav|tab|menu', re.I))
        print(f"\n🧭 Найдено навигационных элементов: {len(nav_elements)}")
        
        for i, nav in enumerate(nav_elements[:3]):
            print(f"  {i+1}. {nav.name} class='{nav.get('class', [])}'")
        
        # Ищем контейнеры с контентом
        content_containers = soup.find_all(['div', 'section'], class_=re.compile(r'content|chapter|list', re.I))
        print(f"\n📦 Найдено контейнеров контента: {len(content_containers)}")
        
        for i, container in enumerate(content_containers[:3]):
            print(f"  {i+1}. {container.name} class='{container.get('class', [])}'")
        
        # Ищем скрипты
        scripts = soup.find_all('script')
        print(f"\n📜 Найдено скриптов: {len(scripts)}")
        
        # Ищем элементы с data-атрибутами
        data_elements = soup.find_all(attrs={"data-": True})
        print(f"\n💾 Найдено элементов с data-атрибутами: {len(data_elements)}")
        
        # Сохраняем HTML для анализа
        with open('novelbins_page.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"\n💾 HTML сохранен в файл: novelbins_page.html")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при анализе: {e}")
        return False

if __name__ == "__main__":
    analyze_novelbins_structure() 