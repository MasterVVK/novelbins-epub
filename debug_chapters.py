#!/usr/bin/env python3
"""
Скрипт для диагностики глав в базе данных
"""

import sys
sys.path.insert(0, 'web_app')

from web_app.app import create_app
from web_app.app.models import Novel, Chapter


def debug_chapters(novel_id=None):
    """Показать информацию о главах"""

    app = create_app()
    with app.app_context():

        # Получаем все новеллы или конкретную
        if novel_id:
            novels = [Novel.query.get(novel_id)]
            if not novels[0]:
                print(f"❌ Новелла с ID {novel_id} не найдена!")
                return
        else:
            novels = Novel.query.filter_by(is_active=True).all()

        for novel in novels:
            if not novel:
                continue

            print("\n" + "=" * 70)
            print(f"📚 Новелла: {novel.title} (ID: {novel.id})")
            print("=" * 70)

            # Получаем главы
            chapters = Chapter.query.filter_by(novel_id=novel.id).order_by(Chapter.chapter_number).all()

            print(f"\n📊 Всего глав: {len(chapters)}")

            # Статистика
            with_original = sum(1 for ch in chapters if ch.original_text)
            with_translation = sum(1 for ch in chapters if ch.current_translation)
            with_edited = sum(1 for ch in chapters if ch.edited_translation)

            print(f"   С оригинальным текстом: {with_original}")
            print(f"   С переводом: {with_translation}")
            print(f"   С редактурой: {with_edited}")

            # Показываем первые 5 глав
            print("\n📖 Первые 5 глав:")
            for ch in chapters[:5]:
                print(f"\n   Глава {ch.chapter_number}:")
                print(f"      Заголовок: {ch.original_title}")
                print(f"      Статус: {ch.status}")
                print(f"      Оригинал: {'✅ Есть' if ch.original_text else '❌ Нет'} ({len(ch.original_text or '') if ch.original_text else 0} символов)")
                print(f"      Перевод: {'✅ Есть' if ch.current_translation else '❌ Нет'}")
                print(f"      Редактура: {'✅ Есть' if ch.edited_translation else '❌ Нет'}")

                if ch.original_text:
                    print(f"      Превью оригинала: {ch.original_text[:100]}...")


def main():
    """Главная функция"""

    print("\n🔍 ДИАГНОСТИКА ГЛАВ В БАЗЕ ДАННЫХ")

    # Если передан аргумент - показываем конкретную новеллу
    if len(sys.argv) > 1:
        try:
            novel_id = int(sys.argv[1])
            debug_chapters(novel_id)
        except ValueError:
            print("❌ Неверный ID новеллы. Используйте: python debug_chapters.py <novel_id>")
    else:
        # Показываем все новеллы
        debug_chapters()

    print("\n")


if __name__ == '__main__':
    main()
