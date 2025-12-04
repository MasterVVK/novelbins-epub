#!/usr/bin/env python3
"""
Анализ потерянных фрагментов текста при сопоставлении
Новелла 21, Глава 1
"""
import sys
import re
from pathlib import Path
from difflib import SequenceMatcher

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'web_app'))

from app import create_app
from app.models import Chapter, BilingualAlignment, Translation

app = create_app()


def split_sentences(text, language='ru'):
    """Разбиение текста на предложения"""
    if language == 'zh':
        # Китайский: разделители 。！？
        sentences = re.split(r'([。！？])', text)
    else:
        # Русский: разделители .!?
        sentences = re.split(r'([.!?])', text)

    # Объединяем предложение с разделителем
    result = []
    for i in range(0, len(sentences) - 1, 2):
        if i + 1 < len(sentences):
            sent = sentences[i] + sentences[i + 1]
            sent = sent.strip()
            if sent:
                result.append(sent)

    # Последнее предложение без разделителя
    if len(sentences) % 2 == 1 and sentences[-1].strip():
        result.append(sentences[-1].strip())

    return result


def find_similar(text, text_list, threshold=0.8):
    """Поиск похожего текста в списке"""
    text_lower = text.lower().strip()

    for item in text_list:
        item_lower = item.lower().strip()

        # Точное совпадение
        if text_lower == item_lower:
            return True, 1.0

        # Проверка вхождения
        if text_lower in item_lower or item_lower in text_lower:
            return True, 0.9

        # Схожесть через SequenceMatcher
        ratio = SequenceMatcher(None, text_lower, item_lower).ratio()
        if ratio >= threshold:
            return True, ratio

    return False, 0.0


def analyze_lost_text():
    """Анализ потерянных фрагментов"""
    with app.app_context():
        # Получаем данные
        chapter = Chapter.query.filter_by(novel_id=21, chapter_number=1).first()
        translation = Translation.query.filter_by(
            chapter_id=chapter.id,
            translation_type='edited'
        ).first()
        alignment = BilingualAlignment.query.filter_by(chapter_id=chapter.id).first()

        if not all([chapter, translation, alignment]):
            print("❌ Данные не найдены")
            return

        # Исходные тексты
        russian_text = translation.translated_text
        chinese_text = chapter.original_text

        # Выровненные фрагменты
        alignments = alignment.alignment_data.get('alignments', [])

        aligned_ru_fragments = [pair['ru'] for pair in alignments]
        aligned_zh_fragments = [pair['zh'] for pair in alignments]

        print("=" * 80)
        print("🔍 АНАЛИЗ ПОТЕРЯННЫХ ФРАГМЕНТОВ")
        print("=" * 80)

        # Анализ русского текста
        print("\n📝 АНАЛИЗ РУССКОГО ТЕКСТА:")
        print(f"Исходный текст: {len(russian_text)} символов")

        ru_sentences = split_sentences(russian_text, 'ru')
        print(f"Предложений: {len(ru_sentences)}")

        ru_lost = []
        ru_found = 0

        for sent in ru_sentences:
            found, ratio = find_similar(sent, aligned_ru_fragments, threshold=0.7)
            if found:
                ru_found += 1
            else:
                ru_lost.append(sent)

        print(f"Найдено в выравнивании: {ru_found}/{len(ru_sentences)}")
        print(f"Потеряно: {len(ru_lost)} предложений")

        if ru_lost:
            print(f"\n❌ ПОТЕРЯННЫЕ РУССКИЕ ФРАГМЕНТЫ:")
            for i, sent in enumerate(ru_lost, 1):
                print(f"  [{i}] {sent[:100]}{'...' if len(sent) > 100 else ''}")

        # Анализ китайского текста
        print("\n" + "=" * 80)
        print("📝 АНАЛИЗ КИТАЙСКОГО ТЕКСТА:")
        print(f"Исходный текст: {len(chinese_text)} символов")

        zh_sentences = split_sentences(chinese_text, 'zh')
        print(f"Предложений: {len(zh_sentences)}")

        zh_lost = []
        zh_found = 0

        for sent in zh_sentences:
            found, ratio = find_similar(sent, aligned_zh_fragments, threshold=0.7)
            if found:
                zh_found += 1
            else:
                zh_lost.append(sent)

        print(f"Найдено в выравнивании: {zh_found}/{len(zh_sentences)}")
        print(f"Потеряно: {len(zh_lost)} предложений")

        if zh_lost:
            print(f"\n❌ ПОТЕРЯННЫЕ КИТАЙСКИЕ ФРАГМЕНТЫ:")
            for i, sent in enumerate(zh_lost, 1):
                print(f"  [{i}] {sent}")

        # Анализ объемов потерь
        print("\n" + "=" * 80)
        print("📊 СТАТИСТИКА ПОТЕРЬ:")

        ru_lost_chars = sum(len(s) for s in ru_lost)
        zh_lost_chars = sum(len(s) for s in zh_lost)

        print(f"\nРусский:")
        print(f"  Потеряно символов: {ru_lost_chars}/{len(russian_text)} ({ru_lost_chars/len(russian_text)*100:.2f}%)")
        print(f"  Потеряно предложений: {len(ru_lost)}/{len(ru_sentences)} ({len(ru_lost)/len(ru_sentences)*100:.2f}%)")

        print(f"\nКитайский:")
        print(f"  Потеряно символов: {zh_lost_chars}/{len(chinese_text)} ({zh_lost_chars/len(chinese_text)*100:.2f}%)")
        print(f"  Потеряно предложений: {len(zh_lost)}/{len(zh_sentences)} ({len(zh_lost)/len(zh_sentences)*100:.2f}%)")

        print("\n" + "=" * 80)


if __name__ == '__main__':
    analyze_lost_text()
