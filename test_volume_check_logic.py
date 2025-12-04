#!/usr/bin/env python3
"""
Тест логики проверки объема на существующем сопоставлении
Новелла 21, Глава 1
"""
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'web_app'))

from app import create_app
from app.models import Chapter, BilingualAlignment, Translation
from app.services.bilingual_alignment_service import BilingualAlignmentService

app = create_app()


def test_volume_check():
    """Тест проверки объема на существующих данных"""
    with app.app_context():
        # Загружаем главу
        chapter = Chapter.query.filter_by(novel_id=21, chapter_number=1).first()

        if not chapter:
            print("❌ Глава не найдена")
            return

        # Загружаем перевод
        translation = Translation.query.filter_by(
            chapter_id=chapter.id,
            translation_type='edited'
        ).first()

        if not translation:
            print("❌ Перевод не найден")
            return

        # Загружаем сопоставление
        alignment = BilingualAlignment.query.filter_by(chapter_id=chapter.id).first()

        if not alignment:
            print("❌ Сопоставление не найдено")
            return

        print("=" * 80)
        print("🔍 ТЕСТ ЛОГИКИ ПРОВЕРКИ ОБЪЕМА")
        print("=" * 80)

        print(f"\n📖 Новелла: {chapter.novel_id}, Глава: {chapter.chapter_number}")

        # Исходные данные
        russian_text = translation.translated_text
        chinese_text = chapter.original_text
        alignments = alignment.alignment_data.get('alignments', [])

        print(f"\n📊 ИСХОДНЫЕ ДАННЫЕ:")
        print(f"  Русский текст:    {len(russian_text)} символов")
        print(f"  Китайский текст:  {len(chinese_text)} символов")
        print(f"  Количество пар:   {len(alignments)}")

        # Создаем сервис и вызываем метод проверки
        service = BilingualAlignmentService()

        print(f"\n🔬 ПРОВЕРКА ОБЪЕМА (минимум 95% покрытия):")

        # Тест с разными порогами
        for min_coverage in [0.95, 0.90, 0.85]:
            is_valid, stats = service._check_volume_integrity(
                alignments,
                russian_text,
                chinese_text,
                min_coverage=min_coverage
            )

            print(f"\n  Порог покрытия: {min_coverage * 100:.0f}%")
            print(f"    Исходный RU:     {stats['original_ru_length']} символов")
            print(f"    Сопоставлено RU: {stats['aligned_ru_length']} символов")
            print(f"    Покрытие RU:     {stats['coverage_ru_percent']} {'✅' if stats['coverage_ru'] >= min_coverage else '❌'}")

            print(f"    Исходный ZH:     {stats['original_zh_length']} символов")
            print(f"    Сопоставлено ZH: {stats['aligned_zh_length']} символов")
            print(f"    Покрытие ZH:     {stats['coverage_zh_percent']} {'✅' if stats['coverage_zh'] >= min_coverage else '❌'}")

            print(f"    Результат:       {'✅ ВАЛИДНО' if is_valid else '❌ НЕ ВАЛИДНО'}")

        # Детальная статистика
        is_valid, stats = service._check_volume_integrity(
            alignments,
            russian_text,
            chinese_text,
            min_coverage=0.95
        )

        print(f"\n📈 ДЕТАЛЬНАЯ СТАТИСТИКА (порог 95%):")
        print(f"  Потеря RU: {stats['original_ru_length'] - stats['aligned_ru_length']} символов ({100 - stats['coverage_ru'] * 100:.2f}%)")
        print(f"  Потеря ZH: {stats['original_zh_length'] - stats['aligned_zh_length']} символов ({100 - stats['coverage_zh'] * 100:.2f}%)")

        if is_valid:
            print(f"\n✅ ПРОВЕРКА ПРОЙДЕНА: Объем текста сохранён (≥95%)")
        else:
            print(f"\n⚠️ ПРОВЕРКА НЕ ПРОЙДЕНА: Обнаружена потеря текста")
            print(f"   Система автоматически повторит запрос к LLM")

        print("\n" + "=" * 80)


if __name__ == '__main__':
    test_volume_check()
