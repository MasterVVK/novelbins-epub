"""
Модуль для выравнивания русского и китайского текста на уровне предложений
"""
import re
from typing import List, Tuple


class BilingualTextAligner:
    """Класс для выравнивания русского и китайского текста"""

    @staticmethod
    def split_into_sentences(text: str, language: str = 'ru') -> List[str]:
        """
        Разбивает текст на предложения

        Args:
            text: Исходный текст
            language: Язык текста ('ru' для русского, 'zh' для китайского)

        Returns:
            Список предложений
        """
        if not text:
            return []

        if language == 'zh':
            # Китайский: разбиваем по китайским знакам препинания
            # 。！？；：
            sentences = re.split(r'([。！？；])', text)

            # Объединяем знаки препинания с предложениями
            result = []
            for i in range(0, len(sentences) - 1, 2):
                sentence = sentences[i].strip()
                punctuation = sentences[i + 1] if i + 1 < len(sentences) else ''
                if sentence:
                    result.append(sentence + punctuation)

            # Добавляем последнее предложение, если есть
            if len(sentences) % 2 == 1 and sentences[-1].strip():
                result.append(sentences[-1].strip())

            return result

        else:  # ru или другие языки с латиницей/кириллицей
            # Русский: разбиваем по точке, восклицательному и вопросительному знакам
            # Но игнорируем сокращения типа "г-н", "т.д." и т.п.

            # Разбиваем по знакам препинания, сохраняя их
            sentences = re.split(r'([.!?…]+\s*)', text)

            # Объединяем знаки препинания с предложениями
            result = []
            temp_sentence = ""

            for i, part in enumerate(sentences):
                temp_sentence += part

                # Если это знак препинания
                if re.match(r'[.!?…]+\s*', part):
                    # Проверяем, не является ли это сокращением
                    # Простая эвристика: если следующая часть начинается с маленькой буквы,
                    # то это продолжение предложения
                    if i + 1 < len(sentences):
                        next_part = sentences[i + 1].strip()
                        if next_part and not next_part[0].isupper():
                            continue  # Продолжаем накапливать

                    # Иначе сохраняем предложение
                    if temp_sentence.strip():
                        result.append(temp_sentence.strip())
                        temp_sentence = ""

            # Добавляем остаток, если есть
            if temp_sentence.strip():
                result.append(temp_sentence.strip())

            return result

    @staticmethod
    def align_sentences(russian_text: str, chinese_text: str) -> List[Tuple[str, str]]:
        """
        Выравнивает русские и китайские предложения

        Args:
            russian_text: Русский текст
            chinese_text: Китайский текст

        Returns:
            Список пар (русское_предложение, китайское_предложение)
        """
        ru_sentences = BilingualTextAligner.split_into_sentences(russian_text, 'ru')
        zh_sentences = BilingualTextAligner.split_into_sentences(chinese_text, 'zh')

        # Простое выравнивание: предполагаем, что количество предложений совпадает
        # Если не совпадает, используем минимальное количество
        min_len = min(len(ru_sentences), len(zh_sentences))

        aligned = []
        for i in range(min_len):
            aligned.append((ru_sentences[i], zh_sentences[i]))

        # Если одного из языков больше предложений, добавляем их с пустыми парами
        if len(ru_sentences) > min_len:
            for i in range(min_len, len(ru_sentences)):
                aligned.append((ru_sentences[i], ''))
        elif len(zh_sentences) > min_len:
            for i in range(min_len, len(zh_sentences)):
                aligned.append(('', zh_sentences[i]))

        return aligned

    @staticmethod
    def align_paragraphs(russian_text: str, chinese_text: str) -> List[Tuple[str, str]]:
        """
        Выравнивает русские и китайские абзацы

        Args:
            russian_text: Русский текст
            chinese_text: Китайский текст

        Returns:
            Список пар (русский_абзац, китайский_абзац)
        """
        ru_paragraphs = [p.strip() for p in russian_text.split('\n\n') if p.strip()]
        zh_paragraphs = [p.strip() for p in chinese_text.split('\n\n') if p.strip()]

        min_len = min(len(ru_paragraphs), len(zh_paragraphs))

        aligned = []
        for i in range(min_len):
            aligned.append((ru_paragraphs[i], zh_paragraphs[i]))

        # Добавляем оставшиеся абзацы
        if len(ru_paragraphs) > min_len:
            for i in range(min_len, len(ru_paragraphs)):
                aligned.append((ru_paragraphs[i], ''))
        elif len(zh_paragraphs) > min_len:
            for i in range(min_len, len(zh_paragraphs)):
                aligned.append(('', zh_paragraphs[i]))

        return aligned

    @staticmethod
    def format_for_epub(aligned_pairs: List[Tuple[str, str]],
                       mode: str = 'sentence',
                       style: str = 'alternating') -> str:
        """
        Форматирует выравненные пары для EPUB

        Args:
            aligned_pairs: Список пар (русский, китайский)
            mode: 'sentence' или 'paragraph'
            style: 'alternating' (чередование) или 'parallel' (параллельно)

        Returns:
            HTML-строка для EPUB
        """
        if style == 'alternating':
            # Чередование: сначала русский, потом китайский
            html_parts = []
            for ru, zh in aligned_pairs:
                if ru:
                    html_parts.append(f'<p class="russian-sentence">{ru}</p>')
                if zh:
                    html_parts.append(f'<p class="chinese-sentence">{zh}</p>')
            return '\n'.join(html_parts)

        elif style == 'parallel':
            # Параллельный текст: русский и китайский в одной строке
            html_parts = []
            for ru, zh in aligned_pairs:
                html_parts.append(f'''
                <div class="parallel-row">
                    <div class="russian-column">{ru if ru else ''}</div>
                    <div class="chinese-column">{zh if zh else ''}</div>
                </div>
                ''')
            return '\n'.join(html_parts)

        else:
            raise ValueError(f"Unknown style: {style}")
