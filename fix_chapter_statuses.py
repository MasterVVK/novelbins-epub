#!/usr/bin/env python3
"""
Скрипт для исправления статусов глав в новелле 12.
Меняет статус с 'edited' на 'translated' для глав, где отредактированный текст
меньше или равен переведенному (что указывает на проблемы с редактурой).
"""

import sys
import os
import logging

# КРИТИЧЕСКИ ВАЖНО: Настраиваем логирование ДО импорта приложения
# Полностью отключаем SQL логи - удаляем все хендлеры и устанавливаем максимальный уровень
for logger_name in ['sqlalchemy', 'sqlalchemy.engine', 'sqlalchemy.engine.Engine', 'sqlalchemy.pool']:
    logger = logging.getLogger(logger_name)
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.CRITICAL)

# Устанавливаем переменную окружения для отключения SQLALCHEMY_ECHO
os.environ['SQLALCHEMY_ECHO'] = 'False'

# Добавляем путь к приложению
sys.path.insert(0, '/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Chapter, Translation

def fix_chapter_statuses(novel_id=12, dry_run=True):
    """
    Исправление статусов глав

    Args:
        novel_id: ID новеллы
        dry_run: Если True, только показывает что будет изменено (не сохраняет в БД)
    """
    app = create_app()

    # Дополнительная страховка - отключаем ECHO
    app.config['SQLALCHEMY_ECHO'] = False

    # Радикальный подход: заменяем все обработчики на NullHandler
    null_handler = logging.NullHandler()
    for logger_name in ['sqlalchemy', 'sqlalchemy.engine', 'sqlalchemy.engine.Engine',
                        'sqlalchemy.pool', 'sqlalchemy.dialects', 'sqlalchemy.orm']:
        logger = logging.getLogger(logger_name)
        logger.handlers = [null_handler]
        logger.propagate = False
        logger.setLevel(logging.CRITICAL + 100)  # Выше любого уровня

    with app.app_context():
        # Получаем все главы со статусом 'edited'
        chapters = Chapter.query.filter_by(
            novel_id=novel_id,
            status='edited'
        ).order_by(Chapter.chapter_number).all()

        print(f"📊 Всего глав со статусом 'edited': {len(chapters)}")
        print(f"🔍 Проверяем размеры текстов...")
        print()

        problematic_chapters = []

        for chapter in chapters:
            # Получаем переведенный текст (initial)
            initial_translation = Translation.query.filter_by(
                chapter_id=chapter.id,
                translation_type='initial'
            ).order_by(Translation.created_at.desc()).first()

            # Получаем отредактированный текст (edited)
            edited_translation = Translation.query.filter_by(
                chapter_id=chapter.id,
                translation_type='edited'
            ).order_by(Translation.created_at.desc()).first()

            if not initial_translation or not edited_translation:
                continue

            initial_length = len(initial_translation.translated_text) if initial_translation.translated_text else 0
            edited_length = len(edited_translation.translated_text) if edited_translation.translated_text else 0

            # Проверяем: если edited <= initial, это проблема
            if edited_length <= initial_length:
                diff = edited_length - initial_length
                problematic_chapters.append({
                    'chapter': chapter,
                    'initial_length': initial_length,
                    'edited_length': edited_length,
                    'diff': diff
                })

        print(f"❌ Найдено проблемных глав: {len(problematic_chapters)}")
        print()

        if not problematic_chapters:
            print("✅ Нет глав для исправления!")
            return

        # Показываем первые 20 для примера
        print("📋 Первые 20 проблемных глав:")
        print(f"{'ID':<7} {'Глава':<7} {'Initial':<10} {'Edited':<10} {'Diff':<10}")
        print("-" * 55)

        for item in problematic_chapters[:20]:
            ch = item['chapter']
            print(f"{ch.id:<7} {ch.chapter_number:<7} {item['initial_length']:<10} {item['edited_length']:<10} {item['diff']:<10}")

        if len(problematic_chapters) > 20:
            print(f"... и еще {len(problematic_chapters) - 20} глав")

        print()

        if dry_run:
            print("🔒 Режим DRY RUN - изменения НЕ будут сохранены в БД")
            print(f"   Будет изменено глав: {len(problematic_chapters)}")
            print()
            print("Для применения изменений запустите с параметром: --apply")
        else:
            print("💾 Применяем изменения...")

            updated_count = 0
            for item in problematic_chapters:
                chapter = item['chapter']
                chapter.status = 'translated'
                updated_count += 1

                if updated_count % 50 == 0:
                    print(f"   Обновлено: {updated_count}/{len(problematic_chapters)}")

            db.session.commit()

            print()
            print(f"✅ Успешно обновлено глав: {updated_count}")
            print(f"   Статус изменен с 'edited' на 'translated'")

        print()
        print("📊 Итоговая статистика:")
        print(f"   Всего проверено глав: {len(chapters)}")
        print(f"   Проблемных глав: {len(problematic_chapters)} ({len(problematic_chapters)/len(chapters)*100:.1f}%)")
        print(f"   Нормальных глав: {len(chapters) - len(problematic_chapters)}")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Исправление статусов глав',
        epilog='''
Примеры использования:

  # Просмотр изменений (dry run):
  python %(prog)s

  # Применить изменения:
  python %(prog)s --apply

  # Скрыть SQL логи (рекомендуется):
  python %(prog)s 2>&1 | grep -v "sqlalchemy" | grep -v "INFO"

  # Применить изменения без SQL логов:
  python %(prog)s --apply 2>&1 | grep -v "sqlalchemy" | grep -v "INFO"
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--novel-id', type=int, default=12, help='ID новеллы (по умолчанию: 12)')
    parser.add_argument('--apply', action='store_true', help='Применить изменения (иначе dry run)')

    args = parser.parse_args()

    print("=" * 60)
    print("🔧 Скрипт исправления статусов глав")
    print("=" * 60)
    print()

    fix_chapter_statuses(novel_id=args.novel_id, dry_run=not args.apply)

    print()
    print("=" * 60)
    print("✅ Готово!")
    print("=" * 60)
