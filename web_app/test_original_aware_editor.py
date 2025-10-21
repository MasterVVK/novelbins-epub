#!/usr/bin/env python3
"""
Тестовый скрипт для проверки OriginalAwareEditorService
на новелле "Одна мысль о вечности" (一念永恒)
"""

import sys
import os
import time
import logging
from pathlib import Path

# Добавляем путь к web_app
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app, db
from app.models import Novel, Chapter, Translation
from app.services.original_aware_editor_service import OriginalAwareEditorService
from app.services.translator_service import TranslatorService

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def test_single_chapter(novel_id=11, chapter_number=1):
    """
    Тестирование редактирования одной главы
    """
    app = create_app()

    with app.app_context():
        print("\n" + "="*70)
        print("ТЕСТИРОВАНИЕ OriginalAwareEditorService")
        print("="*70 + "\n")

        # Получаем новеллу
        novel = Novel.query.get(novel_id)
        if not novel:
            print(f"❌ Новелла с ID {novel_id} не найдена!")
            return False

        print(f"📚 Новелла: {novel.title}")
        print(f"   Оригинальное название: {novel.original_title}")
        print(f"   Автор: {novel.author if novel.author else 'Не указан'}")
        print(f"   Всего глав: {novel.total_chapters}")
        print(f"   Переведено: {novel.translated_chapters}")
        print(f"   Отредактировано: {novel.edited_chapters}")
        print()

        # Получаем главу для тестирования
        chapter = Chapter.query.filter_by(
            novel_id=novel_id,
            chapter_number=chapter_number
        ).first()

        if not chapter:
            print(f"❌ Глава {chapter_number} не найдена!")
            return False

        print(f"📖 Глава для тестирования: #{chapter.chapter_number}")
        print(f"   Статус: {chapter.status}")

        # Проверяем наличие оригинального текста
        if not chapter.original_text:
            print(f"❌ Оригинальный текст отсутствует!")
            return False
        print(f"   Оригинальный текст: {len(chapter.original_text)} символов")

        # Проверяем наличие перевода
        translation = Translation.query.filter_by(
            chapter_id=chapter.id,
            translation_type='initial'
        ).order_by(Translation.created_at.desc()).first()

        if not translation:
            print(f"❌ Перевод главы не найден!")
            return False
        print(f"   Переведенный текст: {len(translation.translated_text)} символов")
        print(f"   Качество перевода: {translation.quality_score}/10")

        # Проверяем глоссарий
        from app.services.glossary_service import GlossaryService
        glossary_items = GlossaryService.get_glossary_for_novel(novel_id)
        print(f"   Глоссарий: {len(glossary_items)} терминов")
        print()

        print("="*70)
        print("НАЧИНАЕМ РЕДАКТИРОВАНИЕ С ОРИГИНАЛОМ И ГЛОССАРИЕМ")
        print("="*70 + "\n")

        # Создаем сервис редактирования
        translator_service = TranslatorService()
        editor = OriginalAwareEditorService(translator_service)

        # Показываем первые 500 символов оригинала
        print("📝 Фрагмент ОРИГИНАЛА:")
        print("-"*50)
        print(chapter.original_text[:500])
        print("-"*50 + "\n")

        # Показываем первые 500 символов перевода
        print("📝 Фрагмент ПЕРЕВОДА (до редактирования):")
        print("-"*50)
        print(translation.translated_text[:500])
        print("-"*50 + "\n")

        # Засекаем время
        start_time = time.time()

        # ЗАПУСКАЕМ РЕДАКТИРОВАНИЕ
        print("🚀 Запускаем редактирование...")
        print("   (это может занять 30-60 секунд)")
        print()

        try:
            result = editor.edit_chapter(chapter)

            if result:
                elapsed = time.time() - start_time
                print(f"\n✅ УСПЕШНО! Глава отредактирована за {elapsed:.1f} секунд")

                # Получаем отредактированную версию
                edited = Translation.query.filter_by(
                    chapter_id=chapter.id,
                    translation_type='edited'
                ).order_by(Translation.created_at.desc()).first()

                if edited:
                    print(f"\n📊 Результаты редактирования:")
                    print(f"   Качество: {edited.quality_score}/10 (было {translation.quality_score}/10)")
                    print(f"   Длина текста: {len(edited.translated_text)} символов")

                    # Показываем метаданные
                    if edited.context_used:
                        context = edited.context_used
                        print(f"\n📈 Метаданные:")
                        print(f"   Использовано терминов глоссария: {context.get('glossary_terms_used', 0)}")
                        print(f"   Критических терминов: {context.get('critical_terms', 0)}")
                        print(f"   Длина оригинала: {context.get('original_text_length', 0)}")
                        print(f"   Использован оригинал: {'Да' if context.get('used_original') else 'Нет'}")
                        print(f"   Использован глоссарий: {'Да' if context.get('used_full_glossary') else 'Нет'}")

                    # Показываем первые 500 символов результата
                    print("\n📝 Фрагмент ПОСЛЕ редактирования:")
                    print("-"*50)
                    print(edited.translated_text[:500])
                    print("-"*50)

                    # Обновляем статистику новеллы
                    novel.update_stats()
                    db.session.commit()

                    print(f"\n✅ Тест завершен успешно!")
                    print(f"   Глава {chapter.chapter_number} отредактирована")
                    print(f"   Новый статус главы: {chapter.status}")
                    return True

            else:
                print(f"\n❌ Ошибка при редактировании главы")
                return False

        except Exception as e:
            print(f"\n❌ Исключение при редактировании: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_batch_chapters(novel_id=11, start_chapter=1, count=3):
    """
    Тестирование редактирования нескольких глав
    """
    app = create_app()

    with app.app_context():
        print("\n" + "="*70)
        print(f"ПАКЕТНОЕ РЕДАКТИРОВАНИЕ ({count} глав)")
        print("="*70 + "\n")

        # Получаем новеллу
        novel = Novel.query.get(novel_id)
        if not novel:
            print(f"❌ Новелла с ID {novel_id} не найдена!")
            return False

        print(f"📚 Новелла: {novel.title}")

        # Создаем сервис
        translator_service = TranslatorService()
        editor = OriginalAwareEditorService(translator_service)

        success_count = 0

        for i in range(count):
            chapter_num = start_chapter + i

            # Получаем главу
            chapter = Chapter.query.filter_by(
                novel_id=novel_id,
                chapter_number=chapter_num
            ).first()

            if not chapter:
                print(f"⚠️ Глава {chapter_num} не найдена, пропускаем")
                continue

            if chapter.status == 'edited':
                print(f"⏭️ Глава {chapter_num} уже отредактирована, пропускаем")
                continue

            print(f"\n📖 Редактируем главу {chapter_num}...")

            try:
                result = editor.edit_chapter(chapter)
                if result:
                    success_count += 1
                    print(f"   ✅ Успешно отредактирована")
                else:
                    print(f"   ❌ Ошибка редактирования")

            except Exception as e:
                print(f"   ❌ Исключение: {e}")

        print(f"\n📊 Итоги:")
        print(f"   Отредактировано: {success_count} из {count} глав")

        # Обновляем статистику
        novel.update_stats()
        db.session.commit()

        print(f"   Всего отредактировано в новелле: {novel.edited_chapters}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Тестирование OriginalAwareEditorService')
    parser.add_argument('--novel-id', type=int, default=11,
                       help='ID новеллы (по умолчанию: 11 - Одна мысль о вечности)')
    parser.add_argument('--chapter', type=int, default=1,
                       help='Номер главы для тестирования (по умолчанию: 1)')
    parser.add_argument('--batch', action='store_true',
                       help='Редактировать несколько глав')
    parser.add_argument('--count', type=int, default=3,
                       help='Количество глав для пакетного редактирования (по умолчанию: 3)')

    args = parser.parse_args()

    if args.batch:
        # Пакетное редактирование
        test_batch_chapters(args.novel_id, args.chapter, args.count)
    else:
        # Редактирование одной главы
        test_single_chapter(args.novel_id, args.chapter)