#!/usr/bin/env python3
"""
Скрипт для извлечения названий из уже переведённых глав

Применяет функцию extract_title_and_content() к существующим переводам
и обновляет поле translated_title в БД.
"""
import sys
import os

# Добавляем путь к web_app
sys.path.insert(0, '/home/user/novelbins-epub/web_app')
os.environ['DATABASE_URL'] = 'postgresql://novelbins_user:novelbins_strong_pass_2025@localhost:5432/novelbins_epub'

from app import create_app, db
from app.models.chapter import Chapter
from app.models.translation import Translation
from app.models.glossary import GlossaryItem
from app.services.translator_service import TranslatorService

def fix_missing_titles(novel_id=None, dry_run=False, limit=None, yes=False):
    """
    Извлекает названия из переведённых текстов

    Args:
        novel_id: ID новеллы (если None - обрабатываются все)
        dry_run: Если True, только показывает что будет сделано без изменений
        limit: Максимальное количество глав для обработки (для тестирования)
        yes: Автоматическое подтверждение без запроса
    """
    print("=" * 80)
    print("🔧 ИСПРАВЛЕНИЕ ОТСУТСТВУЮЩИХ НАЗВАНИЙ В ПЕРЕВОДАХ")
    print("=" * 80)
    print()

    if dry_run:
        print("⚠️  РЕЖИМ ТЕСТИРОВАНИЯ (dry_run=True) - изменения НЕ будут сохранены")
        print()

    # Создаём Flask app context
    app = create_app()

    with app.app_context():
        # Создаём TranslatorService для использования extract_title_and_content
        translator_service = TranslatorService()

        # Находим все переводы без названий
        query = db.session.query(Translation).join(Chapter)

        if novel_id:
            query = query.filter(Chapter.novel_id == novel_id)
            print(f"📚 Новелла: ID {novel_id}")
        else:
            print("📚 Обрабатываются все новеллы")

        # Фильтруем переводы без названий
        query = query.filter(
            db.or_(
                Translation.translated_title == None,
                Translation.translated_title == ''
            )
        )

        # Применяем лимит, если указан
        if limit:
            query = query.limit(limit)
            print(f"⚠️  ОГРАНИЧЕНИЕ: обрабатываются только первые {limit} глав")

        translations = query.all()

        total = len(translations)

        if total == 0:
            print("✅ Все переводы уже имеют названия!")
            return

        print(f"📊 Найдено переводов без названий: {total}")
        print()

        if not dry_run and not yes:
            confirm = input(f"Продолжить обработку {total} глав? (yes/no): ")
            if confirm.lower() not in ['yes', 'y', 'да', 'д']:
                print("❌ Отменено пользователем")
                return
            print()

        # Статистика
        success_count = 0
        no_title_count = 0
        error_count = 0

        print("🚀 Начинаем обработку...")
        print("-" * 80)

        for i, translation in enumerate(translations, 1):
            chapter = translation.chapter
            novel_title = chapter.novel.title

            try:
                # Извлекаем название из переведённого текста
                if not translation.translated_text:
                    print(f"⚠️  [{i}/{total}] Глава {chapter.chapter_number} ({novel_title}): Нет translated_text")
                    error_count += 1
                    continue

                # Применяем extract_title_and_content
                title, content = translator_service.extract_title_and_content(
                    translation.translated_text
                )

                if title:
                    # Найдено название в тексте
                    print(f"✅ [{i}/{total}] Глава {chapter.chapter_number}: '{title}' (извлечено из текста)")

                    if not dry_run:
                        translation.translated_title = title
                        db.session.commit()

                    success_count += 1
                else:
                    # Название не найдено в тексте - переводим original_title отдельно
                    if chapter.original_title:
                        print(f"🔄 [{i}/{total}] Глава {chapter.chapter_number}: Переводим название отдельно...")

                        try:
                            # Загружаем глоссарий для новеллы (тот же, что использовался при переводе)
                            glossary = GlossaryItem.get_glossary_dict(chapter.novel_id)

                            # Переводим название через специальный метод
                            translated_title = translator_service.translate_title_with_glossary(
                                original_title=chapter.original_title,
                                glossary=glossary,
                                chapter_id=chapter.id
                            )

                            if translated_title:
                                print(f"✅ [{i}/{total}] Глава {chapter.chapter_number}: '{translated_title}' (переведено отдельно)")

                                if not dry_run:
                                    translation.translated_title = translated_title
                                    db.session.commit()

                                success_count += 1
                            else:
                                print(f"⚠️  [{i}/{total}] Глава {chapter.chapter_number}: Не удалось перевести название")
                                no_title_count += 1

                        except Exception as e:
                            print(f"❌ [{i}/{total}] Глава {chapter.chapter_number}: Ошибка при переводе названия - {e}")
                            error_count += 1
                            if not dry_run:
                                db.session.rollback()
                    else:
                        print(f"⚠️  [{i}/{total}] Глава {chapter.chapter_number}: Нет оригинального названия")
                        no_title_count += 1

            except Exception as e:
                print(f"❌ [{i}/{total}] Глава {chapter.chapter_number}: Ошибка - {e}")
                error_count += 1

                if not dry_run:
                    db.session.rollback()

        print("-" * 80)
        print()
        print("📊 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"   ✅ Успешно извлечено названий: {success_count}")
        print(f"   ⚠️  Названия не найдены: {no_title_count}")
        print(f"   ❌ Ошибки: {error_count}")
        print(f"   📈 Всего обработано: {i}/{total}")

        if dry_run:
            print()
            print("⚠️  Это был тестовый запуск. Запустите без dry_run=True для сохранения изменений.")
        else:
            print()
            print("✅ Обработка завершена! Изменения сохранены в БД.")

        print()
        print("=" * 80)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Извлечение названий из переведённых текстов')
    parser.add_argument('--novel-id', type=int, help='ID новеллы (если не указан - все новеллы)')
    parser.add_argument('--dry-run', action='store_true', help='Тестовый режим без сохранения')
    parser.add_argument('--limit', type=int, help='Максимальное количество глав (для тестирования)')
    parser.add_argument('--yes', '-y', action='store_true', help='Автоматическое подтверждение без запроса')

    args = parser.parse_args()

    try:
        fix_missing_titles(novel_id=args.novel_id, dry_run=args.dry_run, limit=args.limit, yes=args.yes)
    except KeyboardInterrupt:
        print()
        print("⚠️  Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
