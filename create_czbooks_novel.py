#!/usr/bin/env python3
"""
Скрипт для создания новеллы с czbooks.net
Новелла будет создана БЕЗ cookies - cookies можно добавить через Browser Extension
"""

import sys
import os

# Добавляем путь к web_app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'web_app'))

from app import create_app, db
from app.models.novel import Novel

def create_czbooks_novel():
    """Создать новеллу с czbooks.net"""

    app = create_app()

    with app.app_context():
        # Проверяем, не существует ли уже такая новелла
        url = 'https://czbooks.net/n/ul6pe'
        existing = Novel.query.filter_by(source_url=url).first()

        if existing:
            print(f"⚠️  Новелла с URL {url} уже существует!")
            print(f"   ID: {existing.id}")
            print(f"   Название: {existing.title}")
            print(f"   Статус: {existing.status}")
            print()
            print("Хотите удалить существующую? (y/N): ", end='')
            response = input().strip().lower()

            if response == 'y':
                db.session.delete(existing)
                db.session.commit()
                print("✅ Существующая новелла удалена")
            else:
                print("❌ Отменено")
                return existing.id

        # Создаем новую новеллу
        novel = Novel(
            title="Forty Millenniums of Cultivation",  # Название из czbooks
            original_title="修真四万年",  # Оригинальное название
            author="The Enlightened Master Crouching Cow",
            source_url=url,
            source_type='czbooks',  # Используем czbooks парсер
            status='pending',
            is_active=True,

            # Cookies будут добавлены через Browser Extension
            auth_cookies=None,
            auth_enabled=False,

            # Конфигурация
            config={
                'max_chapters': 10,  # Ограничение для тестирования
                'description': 'Test novel from czbooks.net',
                'use_cloudflare_bypass': True
            }
        )

        db.session.add(novel)
        db.session.commit()

        print()
        print("✅ Новелла успешно создана!")
        print()
        print("📚 Информация о новелле:")
        print(f"   ID: {novel.id}")
        print(f"   Название: {novel.title}")
        print(f"   Оригинал: {novel.original_title}")
        print(f"   Автор: {novel.author}")
        print(f"   URL: {novel.source_url}")
        print(f"   Тип источника: {novel.source_type}")
        print(f"   Статус: {novel.status}")
        print()
        print("🔐 Авторизация:")
        print(f"   Auth cookies: {'✅ Установлены' if novel.auth_cookies else '❌ Не установлены'}")
        print(f"   Auth enabled: {novel.auth_enabled}")
        print()
        print("🚀 Следующие шаги:")
        print()
        print("1. Откройте Browser Extension")
        print("   chrome://extensions/")
        print()
        print("2. Перейдите на czbooks.net:")
        print("   https://czbooks.net")
        print()
        print("3. Дождитесь Cloudflare challenge (~5 секунд)")
        print()
        print("4. Откройте расширение и нажмите:")
        print("   [Извлечь Cookies]")
        print()
        print("5. Отправьте cookies в Web App:")
        print("   [Отправить в Web App]")
        print()
        print("6. Обновите новеллу с cookies:")
        print(f"   http://192.168.0.58:5001/edit-novel/{novel.id}")
        print("   Или вставьте cookies при создании новой новеллы")
        print()
        print("7. Запустите парсинг:")
        print(f"   http://192.168.0.58:5001/novel/{novel.id}")
        print()
        print("📖 Документация:")
        print("   browser_extension/QUICK_START.md")
        print("   BROWSER_EXTENSION_READY.md")
        print()

        return novel.id

if __name__ == '__main__':
    try:
        novel_id = create_czbooks_novel()
        print(f"✅ Новелла ID: {novel_id}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
