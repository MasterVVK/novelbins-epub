#!/usr/bin/env python3
"""
Тестовый скрипт для проверки двуязычного выравнивания текста
"""

import sys
sys.path.insert(0, 'web_app')

from web_app.app.utils.text_alignment import BilingualTextAligner


def test_sentence_splitting():
    """Тест разбиения текста на предложения"""

    print("=" * 70)
    print("ТЕСТ: Разбиение текста на предложения")
    print("=" * 70)

    # Пример русского текста
    russian_text = """Эр Лэнцзы широко раскрытыми глазами уставился прямо на чёрную крышу, слепленную из соломы и гнилой грязи. На нём было старое ватное одеяло, которое уже приобрело тёмно-жёлтый цвет. Оно так изменилось, что нельзя было разглядеть его первоначальный вид. От него исходил слабый запах плесени."""

    # Пример китайского текста
    chinese_text = """第一章山边小村 二愣子睁大着双眼，直直望着茅草和烂泥糊成的黑屋顶，身上盖着的旧棉被，已呈深黄色，看不出原来的本来面目，还若有若无的散着淡淡的霉味。"""

    print("\n📝 РУССКИЙ ТЕКСТ:")
    print("-" * 70)
    print(russian_text)

    print("\n🔪 Разбиение на предложения:")
    ru_sentences = BilingualTextAligner.split_into_sentences(russian_text, 'ru')
    for i, sent in enumerate(ru_sentences, 1):
        print(f"{i}. {sent}")

    print("\n" + "=" * 70)
    print("\n📝 КИТАЙСКИЙ ТЕКСТ:")
    print("-" * 70)
    print(chinese_text)

    print("\n🔪 Разбиение на предложения:")
    zh_sentences = BilingualTextAligner.split_into_sentences(chinese_text, 'zh')
    for i, sent in enumerate(zh_sentences, 1):
        print(f"{i}. {sent}")

    return ru_sentences, zh_sentences


def test_alignment():
    """Тест выравнивания предложений"""

    print("\n" + "=" * 70)
    print("ТЕСТ: Выравнивание русских и китайских предложений")
    print("=" * 70)

    russian_text = """Эр Лэнцзы широко раскрытыми глазами уставился прямо на чёрную крышу, слепленную из соломы и гнилой грязи. На нём было старое ватное одеяло, которое уже приобрело тёмно-жёлтый цвет."""

    chinese_text = """二愣子睁大着双眼，直直望着茅草和烂泥糊成的黑屋顶。身上盖着的旧棉被，已呈深黄色。"""

    aligned_pairs = BilingualTextAligner.align_sentences(russian_text, chinese_text)

    print("\n🔗 Выравненные пары:")
    print("-" * 70)
    for i, (ru, zh) in enumerate(aligned_pairs, 1):
        print(f"\nПара {i}:")
        print(f"  RU: {ru}")
        print(f"  ZH: {zh}")

    return aligned_pairs


def test_epub_formatting():
    """Тест форматирования для EPUB"""

    print("\n" + "=" * 70)
    print("ТЕСТ: Форматирование для EPUB")
    print("=" * 70)

    russian_text = """Эр Лэнцзы широко раскрытыми глазами уставился прямо на чёрную крышу, слепленную из соломы и гнилой грязи. На нём было старое ватное одеяло."""

    chinese_text = """二愣子睁大着双眼，直直望着茅草和烂泥糊成的黑屋顶。身上盖着的旧棉被。"""

    aligned_pairs = BilingualTextAligner.align_sentences(russian_text, chinese_text)

    # Чередование
    print("\n📖 Режим: ЧЕРЕДОВАНИЕ (alternating)")
    print("-" * 70)
    html_alternating = BilingualTextAligner.format_for_epub(
        aligned_pairs,
        mode='sentence',
        style='alternating'
    )
    print(html_alternating)

    # Параллельный текст
    print("\n📖 Режим: ПАРАЛЛЕЛЬНЫЙ (parallel)")
    print("-" * 70)
    html_parallel = BilingualTextAligner.format_for_epub(
        aligned_pairs,
        mode='sentence',
        style='parallel'
    )
    print(html_parallel)


def main():
    """Главная функция"""

    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "ТЕСТИРОВАНИЕ ДВУЯЗЫЧНОГО ВЫРАВНИВАНИЯ" + " " * 15 + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        # Тест 1: Разбиение на предложения
        test_sentence_splitting()

        # Тест 2: Выравнивание
        test_alignment()

        # Тест 3: Форматирование для EPUB
        test_epub_formatting()

        print("\n" + "=" * 70)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 70)
        print("\nТеперь вы можете:")
        print("1. Запустить web_app: python web_app/run.py")
        print("2. Перейти к странице новеллы")
        print("3. Нажать кнопку 'Двуязычный EPUB (RU + 中文)'")
        print("4. Скачать и открыть созданный EPUB файл")
        print()

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ ОШИБКА ПРИ ТЕСТИРОВАНИИ!")
        print("=" * 70)
        print(f"\nОшибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
