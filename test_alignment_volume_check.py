#!/usr/bin/env python3
"""
Тест проверки объемов сопоставления на реальных данных
Новелла 21, Глава 1
"""
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'web_app'))

from app import create_app
from app.models import Chapter, BilingualAlignment, Translation

app = create_app()

def test_volume_check():
    """Тест проверки объемов на главе 1 новеллы 21"""
    with app.app_context():
        # Получаем главу
        chapter = Chapter.query.filter_by(novel_id=21, chapter_number=1).first()

        if not chapter:
            print("❌ Глава не найдена")
            return

        # Получаем перевод
        translation = Translation.query.filter_by(
            chapter_id=chapter.id,
            translation_type='edited'
        ).first()

        if not translation:
            print("❌ Перевод не найден")
            return

        # Получаем сопоставление
        alignment = BilingualAlignment.query.filter_by(chapter_id=chapter.id).first()

        if not alignment:
            print("❌ Сопоставление не найдено")
            return

        # Исходные тексты
        russian_text = translation.translated_text
        chinese_text = chapter.original_text

        # Сопоставленные пары
        alignments = alignment.alignment_data.get('alignments', [])

        print("=" * 80)
        print("🧪 ТЕСТ ПРОВЕРКИ ОБЪЕМОВ СОПОСТАВЛЕНИЯ")
        print("=" * 80)
        print(f"\n📖 Новелла: {chapter.novel_id}, Глава: {chapter.chapter_number}")
        print(f"🔗 Всего пар: {len(alignments)}")

        # ИСХОДНЫЕ ОБЪЕМЫ
        original_ru_length = len(russian_text)
        original_zh_length = len(chinese_text)

        print(f"\n📊 ИСХОДНЫЕ ОБЪЕМЫ:")
        print(f"  Русский:   {original_ru_length:6} символов")
        print(f"  Китайский: {original_zh_length:6} символов")

        # ЦИКЛ СЛОЖЕНИЯ
        print(f"\n🔁 ЦИКЛ СЛОЖЕНИЯ ВСЕХ ПАР:")
        aligned_ru_length = 0
        aligned_zh_length = 0

        for i, pair in enumerate(alignments):
            ru_sentence = pair.get('ru', '')
            zh_sentence = pair.get('zh', '')

            ru_len = len(ru_sentence)
            zh_len = len(zh_sentence)

            aligned_ru_length += ru_len
            aligned_zh_length += zh_len

            # Показываем первые 3 и последние 3 пары
            if i < 3 or i >= len(alignments) - 3:
                print(f"  [{i+1:2}] RU: {ru_len:4} символов | ZH: {zh_len:4} символов")
            elif i == 3:
                print(f"  ... (пропущено {len(alignments) - 6} пар)")

        print(f"\n  ✅ Итого сложено:")
        print(f"     Русский:   {aligned_ru_length:6} символов")
        print(f"     Китайский: {aligned_zh_length:6} символов")

        # СРАВНЕНИЕ
        ru_diff = aligned_ru_length - original_ru_length
        zh_diff = aligned_zh_length - original_zh_length

        coverage_ru = aligned_ru_length / original_ru_length
        coverage_zh = aligned_zh_length / original_zh_length

        ru_diff_percent = (coverage_ru - 1) * 100
        zh_diff_percent = (coverage_zh - 1) * 100

        print(f"\n📈 СРАВНЕНИЕ:")
        print(f"  Русский:")
        print(f"    Разница: {ru_diff:+5} символов ({ru_diff_percent:+.2f}%)")
        print(f"    Покрытие: {coverage_ru:.4f} ({coverage_ru*100:.2f}%)")

        print(f"  Китайский:")
        print(f"    Разница: {zh_diff:+5} символов ({zh_diff_percent:+.2f}%)")
        print(f"    Покрытие: {coverage_zh:.4f} ({coverage_zh*100:.2f}%)")

        # ВАЛИДАЦИЯ
        MIN_COVERAGE = 0.95
        MAX_COVERAGE = 1.05

        print(f"\n🎯 ВАЛИДАЦИЯ (критерии: {MIN_COVERAGE*100:.0f}-{MAX_COVERAGE*100:.0f}%):")

        issues = []

        if coverage_ru < MIN_COVERAGE:
            issues.append(f"❌ Потеря русского текста: {ru_diff_percent:.1f}%")
        elif coverage_ru > MAX_COVERAGE:
            issues.append(f"⚠️  Дублирование русского текста: {ru_diff_percent:+.1f}%")
        else:
            print(f"  ✅ Русский текст: {ru_diff_percent:+.1f}% (норма)")

        if coverage_zh < MIN_COVERAGE:
            issues.append(f"❌ Потеря китайского текста: {zh_diff_percent:.1f}%")
        elif coverage_zh > MAX_COVERAGE:
            issues.append(f"⚠️  Дублирование китайского текста: {zh_diff_percent:+.1f}%")
        else:
            print(f"  ✅ Китайский текст: {zh_diff_percent:+.1f}% (норма)")

        if issues:
            print(f"\n⚠️  ОБНАРУЖЕНЫ ПРОБЛЕМЫ:")
            for issue in issues:
                print(f"  {issue}")
            print(f"\n💡 Рекомендация: Повторить запрос к LLM")
        else:
            print(f"\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")

        print("\n" + "=" * 80)

if __name__ == '__main__':
    test_volume_check()
