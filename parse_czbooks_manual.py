#!/usr/bin/env python3
"""
Ручной парсинг czbooks.net новеллы через Xvfb
"""
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'web_app')

from parsers import create_parser_from_url

# Параметры из БД
url = "https://czbooks.net/n/ul6pe"
proxy = "socks5://192.168.0.61:1080"

print("=" * 70)
print("🚀 РУЧНОЙ ПАРСИНГ CZBOOKS.NET")
print("=" * 70)
print(f"URL: {url}")
print(f"Прокси: {proxy}")
print()

# Создаем парсер
print("1️⃣ Создаем парсер...")
parser = create_parser_from_url(url, socks_proxy=proxy, headless=False)
print("   ✅ Парсер создан")
print()

# Получаем список глав
print("2️⃣ Получаем список глав...")
chapters = parser.get_chapter_list(url)
print(f"   ✅ Найдено глав: {len(chapters)}")
print()

if not chapters:
    print("❌ Главы не найдены!")
    parser.close()
    sys.exit(1)

# Показываем первые 10 глав
print("📖 Первые 10 глав:")
for i, ch in enumerate(chapters[:10], 1):
    print(f"   {i}. {ch['title']}")
print()

# Сохраняем в БД
print("3️⃣ Сохраняем главы в БД...")
from app import create_app, db
from app.models import Novel, Chapter

app = create_app()
with app.app_context():
    novel = Novel.query.get(11)
    if not novel:
        print("❌ Новелла ID 11 не найдена в БД")
        parser.close()
        sys.exit(1)

    print(f"   Новелла: {novel.title}")
    print(f"   Сохраняем главы (первые 10 для теста)...")

    saved_count = 0
    for i, ch in enumerate(chapters[:10], 1):  # Первые 10 для теста
        # Проверяем существование
        existing = Chapter.query.filter_by(novel_id=11, chapter_number=i).first()
        if existing:
            print(f"   ⏭️ Глава {i} уже существует")
            continue

        print(f"   💾 Сохраняем главу {i}: {ch['title'][:40]}...")

        # Загружаем контент
        content_data = parser.get_chapter_content(ch['url'])
        if not content_data or not content_data.get('content'):
            print(f"   ⚠️ Не удалось загрузить контент главы {i}")
            continue

        content = content_data['content']

        # Создаем главу
        chapter = Chapter(
            novel_id=11,
            chapter_number=i,
            original_title=ch['title'],
            url=ch['url'],
            original_text=content,
            word_count_original=len(content),
            status='parsed'
        )
        db.session.add(chapter)
        db.session.commit()

        saved_count += 1
        print(f"   ✅ Глава {i} сохранена ({len(content)} символов)")

    # Обновляем статистику новеллы
    novel.total_chapters = len(chapters)
    novel.parsed_chapters = saved_count
    novel.status = 'parsed'
    db.session.commit()

    print()
    print("=" * 70)
    print("✅ ПАРСИНГ ЗАВЕРШЕН!")
    print("=" * 70)
    print(f"Всего глав найдено: {len(chapters)}")
    print(f"Сохранено в БД: {saved_count}")
    print("=" * 70)

parser.close()
