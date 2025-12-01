"""
Утилиты для выделения терминов глоссария в тексте
"""
import re
from typing import List, Dict, Tuple, Set

from app.utils.character_stats import PinyinHelper


class GlossaryHighlighter:
    """Класс для выделения и отслеживания терминов глоссария"""

    @staticmethod
    def highlight_terms_in_text(
        text: str,
        glossary_dict: Dict[str, Dict],
        tag: str = 'strong'
    ) -> Tuple[str, Set[str]]:
        """
        Выделяет термины глоссария в китайском тексте

        Args:
            text: Китайский текст
            glossary_dict: Словарь терминов {chinese_term: {russian, description, category}}
            tag: HTML тег для выделения (по умолчанию 'strong' для жирного)

        Returns:
            (highlighted_text, used_terms_set)
            - highlighted_text: Текст с выделенными терминами
            - used_terms_set: Множество использованных китайских терминов

        Пример:
            text = "林动从洞穴走了出来。"
            glossary = {"林动": {...}}

            → ("<strong>林动</strong>从洞穴走了出来。", {"林动"})
        """
        if not text or not glossary_dict:
            return text, set()

        # ОПТИМИЗАЦИЯ: Предфильтрация - оставляем только термины которые точно есть в тексте
        # Это ускоряет обработку с 4267 терминов до ~10-20 (те что реально в тексте)
        relevant_terms = [term for term in glossary_dict.keys() if term in text]

        if not relevant_terms:
            return text, set()  # Нет терминов в тексте

        # Сортируем термины по длине (от длинных к коротким)
        # Это предотвращает частичные совпадения
        # Например: "涅槃劫" должно выделяться раньше чем "涅槃"
        terms = sorted(relevant_terms, key=len, reverse=True)

        used_terms = set()

        # Словарь для замены: термин → placeholder
        replacements = {}
        placeholder_index = 0

        # Отслеживание уже замененных позиций
        replaced_ranges = []

        for term in terms:
            # Находим все вхождения термина
            pattern = re.escape(term)

            for match in re.finditer(pattern, text):
                start, end = match.span()

                # Проверяем, не пересекается ли с уже замененными диапазонами
                is_overlapping = any(
                    (start < r_end and end > r_start)
                    for r_start, r_end in replaced_ranges
                )

                if not is_overlapping:
                    # Создаем уникальный placeholder
                    placeholder = f"<<<TERM_{placeholder_index}>>>"
                    replacements[placeholder] = term
                    placeholder_index += 1

                    # Добавляем термин в использованные
                    used_terms.add(term)

                    # Отмечаем диапазон как замененный
                    replaced_ranges.append((start, end))

        # Сортируем диапазоны по убыванию позиции (справа налево)
        # Это позволяет заменять без смещения индексов
        replaced_ranges.sort(reverse=True)

        # Применяем замены справа налево
        highlighted_text = text
        placeholder_map = {}

        for i, (start, end) in enumerate(replaced_ranges):
            term = text[start:end]
            if term in glossary_dict:
                placeholder = f"<<<TERM_{i}>>>"
                placeholder_map[placeholder] = term
                highlighted_text = highlighted_text[:start] + placeholder + highlighted_text[end:]

        # Заменяем placeholders на финальные теги
        for placeholder, term in placeholder_map.items():
            highlighted_text = highlighted_text.replace(
                placeholder,
                f"<{tag}>{term}</{tag}>"
            )

        return highlighted_text, used_terms

    @staticmethod
    def format_glossary_section(
        used_terms: Set[str],
        glossary_dict: Dict[str, Dict],
        title: str = "Термины в этой главе",
        include_pinyin: bool = True
    ) -> str:
        """
        Форматирует секцию с терминами для добавления в конец главы

        Args:
            used_terms: Множество использованных китайских терминов
            glossary_dict: Полный словарь глоссария
            title: Заголовок секции
            include_pinyin: Добавлять ли pinyin к терминам

        Returns:
            HTML-строка с форматированным списком терминов

        Пример вывода:
            <div class="glossary-section">
                <h3>Термины в этой главе</h3>
                <dl class="glossary-list">
                    <dt class="glossary-term-zh">林动 (Lín Dòng)</dt>
                    <dd class="glossary-term-ru">Линь Дун</dd>
                    <dd class="glossary-term-desc">Главный герой...</dd>
                </dl>
            </div>
        """
        if not used_terms:
            return ""

        # Группируем термины по категориям
        by_category = {
            'characters': [],
            'locations': [],
            'techniques': [],
            'artifacts': [],
            'terms': []
        }

        for term in sorted(used_terms):
            if term in glossary_dict:
                info = glossary_dict[term]
                category = info.get('category', 'terms')

                if category in by_category:
                    by_category[category].append((term, info))

        # Русские названия категорий
        category_names = {
            'characters': '👤 Персонажи',
            'locations': '📍 Места',
            'techniques': '⚔️ Техники',
            'artifacts': '🔮 Артефакты',
            'terms': '📖 Термины'
        }

        html_parts = [f'<div class="glossary-section">']
        html_parts.append(f'<h3>{title}</h3>')

        for category, terms_list in by_category.items():
            if not terms_list:
                continue

            html_parts.append(f'<h4 class="glossary-category">{category_names[category]}</h4>')
            html_parts.append('<dl class="glossary-list">')

            for zh_term, info in terms_list:
                ru_term = info.get('russian', '')
                description = info.get('description', '')

                # Термин на китайском с pinyin
                if include_pinyin:
                    term_pinyin = PinyinHelper.get_pinyin_for_word(zh_term)
                    html_parts.append(f'  <dt class="glossary-term-zh">{zh_term} <span class="glossary-pinyin">({term_pinyin})</span></dt>')
                else:
                    html_parts.append(f'  <dt class="glossary-term-zh">{zh_term}</dt>')

                # Перевод
                html_parts.append(f'  <dd class="glossary-term-ru">{ru_term}</dd>')

                # Описание (если есть)
                if description:
                    html_parts.append(f'  <dd class="glossary-term-desc">{description}</dd>')

            html_parts.append('</dl>')

        html_parts.append('</div>')

        return '\n'.join(html_parts)

    @staticmethod
    def process_aligned_pairs(
        aligned_pairs: List[Tuple[str, str]],
        glossary_dict: Dict[str, Dict]
    ) -> Tuple[List[Tuple[str, str]], Set[str]]:
        """
        Обрабатывает выравненные пары RU/ZH, выделяя термины в китайском тексте

        Args:
            aligned_pairs: Список пар (ru, zh)
            glossary_dict: Словарь глоссария

        Returns:
            (processed_pairs, all_used_terms)
            - processed_pairs: Список пар с выделенными терминами в zh
            - all_used_terms: Множество всех использованных терминов
        """
        processed_pairs = []
        all_used_terms = set()

        for ru, zh in aligned_pairs:
            if zh:
                # Выделяем термины в китайском тексте
                highlighted_zh, used_terms = GlossaryHighlighter.highlight_terms_in_text(
                    zh, glossary_dict
                )
                processed_pairs.append((ru, highlighted_zh))
                all_used_terms.update(used_terms)
            else:
                processed_pairs.append((ru, zh))

        return processed_pairs, all_used_terms
