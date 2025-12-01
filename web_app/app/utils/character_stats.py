"""
Утилиты для подсчёта статистики иероглифов и добавления pinyin
"""
from collections import Counter
from typing import List, Dict, Set, Tuple, Optional
from pypinyin import pinyin, Style


class PinyinHelper:
    """Класс для работы с pinyin"""

    # Кэш для ускорения повторных запросов
    _cache: Dict[str, str] = {}

    @classmethod
    def get_pinyin(cls, char: str) -> str:
        """
        Получает pinyin для одного иероглифа

        Args:
            char: Китайский иероглиф

        Returns:
            Pinyin с тонами (например: "hǎo")
        """
        if char in cls._cache:
            return cls._cache[char]

        if '\u4e00' <= char <= '\u9fff':
            py = pinyin(char, style=Style.TONE)[0][0]
            cls._cache[char] = py
            return py
        return char

    @classmethod
    def get_pinyin_for_word(cls, word: str) -> str:
        """
        Получает pinyin для слова/фразы

        Args:
            word: Китайское слово или фраза

        Returns:
            Pinyin с пробелами между слогами (например: "nǐ hǎo")
        """
        result = []
        for char in word:
            if '\u4e00' <= char <= '\u9fff':
                result.append(cls.get_pinyin(char))
            else:
                result.append(char)
        return ' '.join(result)

    @classmethod
    def add_ruby_tags(cls, text: str) -> str:
        """
        Добавляет ruby теги с pinyin над каждым иероглифом

        Args:
            text: Китайский текст

        Returns:
            HTML с ruby тегами

        Пример:
            "你好" → "<ruby>你<rt>nǐ</rt></ruby><ruby>好<rt>hǎo</rt></ruby>"
        """
        result = []
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                py = cls.get_pinyin(char)
                result.append(f'<ruby>{char}<rt>{py}</rt></ruby>')
            else:
                result.append(char)
        return ''.join(result)


class CharacterStatsTracker:
    """
    Отслеживание статистики иероглифов по главам
    Использовать один экземпляр на всю книгу при генерации EPUB
    """

    def __init__(self):
        self.global_counter = Counter()  # Общий счётчик по всей книге
        self.seen_chars: Set[str] = set()  # Все встреченные иероглифы
        self.chapter_first_seen: Dict[str, int] = {}  # char → номер главы где впервые

    def process_chapter(self, chapter_num: int, chinese_text: str) -> Dict:
        """
        Обработка одной главы — подсчёт статистики

        Args:
            chapter_num: Номер главы
            chinese_text: Китайский текст главы

        Returns:
            Словарь со статистикой главы:
            {
                'chapter_counts': Counter,  # Счётчик по этой главе
                'top_10': [...],  # Топ-10 с pinyin
                'new_chars': [...],  # Новые иероглифы (впервые в книге)
                'total_chars': int,  # Всего иероглифов в главе
                'unique_chars': int,  # Уникальных в главе
                'total_unique_so_far': int  # Уникальных по всей книге
            }
        """
        # Извлекаем только китайские иероглифы
        chars = [c for c in chinese_text if '\u4e00' <= c <= '\u9fff']
        chapter_counter = Counter(chars)

        # Находим новые иероглифы (впервые встретились в книге)
        current_chars = set(chars)
        new_chars = current_chars - self.seen_chars

        # Запоминаем где впервые встретили
        for char in new_chars:
            self.chapter_first_seen[char] = chapter_num

        # Обновляем глобальную статистику
        self.seen_chars.update(current_chars)
        self.global_counter.update(chars)

        # Формируем топ-20 с pinyin
        top_20 = []
        for char, count in chapter_counter.most_common(20):
            top_20.append({
                'char': char,
                'pinyin': PinyinHelper.get_pinyin(char),
                'count': count
            })

        # Новые иероглифы с pinyin
        new_chars_with_pinyin = []
        for char in sorted(new_chars):
            new_chars_with_pinyin.append({
                'char': char,
                'pinyin': PinyinHelper.get_pinyin(char)
            })

        return {
            'chapter_counts': chapter_counter,
            'top_20': top_20,
            'new_chars': new_chars_with_pinyin,
            'total_chars': len(chars),
            'unique_chars': len(current_chars),
            'total_unique_so_far': len(self.seen_chars)
        }

    def get_book_summary(self) -> Dict:
        """
        Итоговая статистика по всей книге

        Returns:
            {
                'total_chars': int,  # Всего иероглифов
                'unique_chars': int,  # Уникальных
                'top_50': [...],  # Топ-50 самых частых
            }
        """
        top_50 = []
        for char, count in self.global_counter.most_common(50):
            top_50.append({
                'char': char,
                'pinyin': PinyinHelper.get_pinyin(char),
                'count': count
            })

        return {
            'total_chars': sum(self.global_counter.values()),
            'unique_chars': len(self.seen_chars),
            'top_50': top_50
        }


def format_chapter_stats_html(stats: Dict, dictionary=None) -> str:
    """
    Форматирует статистику главы в HTML для EPUB

    Args:
        stats: Результат CharacterStatsTracker.process_chapter()
        dictionary: Экземпляр ChineseRussianDictionary (опционально)

    Returns:
        HTML строка для вставки в конец главы
    """
    # Ленивая загрузка словаря
    if dictionary is None:
        try:
            from app.utils.chinese_dictionary import ChineseRussianDictionary
            dictionary = ChineseRussianDictionary.get_instance()
        except Exception:
            dictionary = None

    html_parts = ['<div class="chapter-stats">']
    html_parts.append('<h3 class="stats-title">📊 Топ-20 иероглифов</h3>')

    # Топ-20 иероглифов в столбик
    html_parts.append('<div class="stats-list">')
    for item in stats['top_20']:
        char = item["char"]
        pinyin = item["pinyin"]
        count = item["count"]

        # Получаем перевод из словаря
        translation = None
        if dictionary and dictionary.is_loaded:
            translation = dictionary.lookup(char)

        if translation:
            html_parts.append(
                f'<p class="stats-item">{char} ({pinyin}) — {translation} [{count}×]</p>'
            )
        else:
            html_parts.append(
                f'<p class="stats-item">{char} ({pinyin}) — {count}×</p>'
            )
    html_parts.append('</div>')

    html_parts.append('</div>')

    return '\n'.join(html_parts)


def format_book_stats_html(stats: Dict) -> str:
    """
    Форматирует итоговую статистику книги в HTML

    Args:
        stats: Результат CharacterStatsTracker.get_book_summary()

    Returns:
        HTML для отдельной страницы статистики
    """
    html_parts = ['<div class="book-stats">']
    html_parts.append('<h2>📚 Статистика книги</h2>')

    html_parts.append('<div class="stats-overview">')
    html_parts.append(f'<p><strong>Всего иероглифов:</strong> {stats["total_chars"]:,}</p>')
    html_parts.append(f'<p><strong>Уникальных иероглифов:</strong> {stats["unique_chars"]:,}</p>')
    html_parts.append('</div>')

    # Топ-50
    html_parts.append('<h3>🏆 Топ-50 самых частых</h3>')
    html_parts.append('<div class="stats-top50">')

    for i, item in enumerate(stats['top_50'], 1):
        html_parts.append(
            f'<span class="top-char">'
            f'{i}. {item["char"]} ({item["pinyin"]}) — {item["count"]:,}×'
            f'</span>'
        )

    html_parts.append('</div>')
    html_parts.append('</div>')

    return '\n'.join(html_parts)
