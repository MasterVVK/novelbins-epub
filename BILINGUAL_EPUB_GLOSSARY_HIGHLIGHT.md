# Выделение терминов глоссария в двуязычном EPUB

## Дата: 2025-11-18

## Цель

При формировании двуязычного EPUB реализовать:
1. **Выделение жирным** китайских иероглифов, которые есть в глоссарии
2. **Список терминов в конце главы** с переводами и описаниями

## Текущая архитектура

### 1. Генерация двуязычного EPUB

**Файл**: `app/services/epub_service.py`

#### Метод `create_bilingual_epub()` (строки 531-631)

```python
def create_bilingual_epub(self, novel_id: int, chapters: List[Dict], config) -> str:
    """Создание двуязычного EPUB с чередованием RU/ZH"""

    # 1. Создание книги и метаданных
    book = epub.EpubBook()
    # ... метаданные ...

    # 2. CSS стили через _get_bilingual_css_styles()
    style = self._get_bilingual_css_styles()

    # 3. Титульная страница, информация, оглавление
    title_page = self._create_bilingual_title_page(novel)
    info_page = self._create_bilingual_info_page()
    toc_page = self._create_bilingual_toc_page(chapters)

    # 4. ГЛАВЫ - ключевой момент!
    for chapter in chapters:
        ch = self._create_bilingual_chapter_page(chapter, nav_css, novel_id)
        book.add_item(ch)
```

#### Метод `_create_bilingual_chapter_page()` (строки 853-951)

```python
def _create_bilingual_chapter_page(self, chapter: Dict, nav_css, novel_id: int):
    """Создание страницы главы с двуязычным содержимым"""

    # 1. Получение главы из БД
    db_chapter = Chapter.query.filter_by(
        novel_id=novel_id,
        chapter_number=chapter['number']
    ).first()

    # 2. LLM-выравнивание через BilingualAlignmentService
    alignment_service = BilingualAlignmentService()
    alignments = alignment_service.align_chapter(
        chapter=db_chapter,
        force_refresh=False,  # Кэш
        save_to_cache=True
    )
    # Формат: [{ru: "...", zh: "...", type: "dialogue", confidence: 0.95}, ...]

    # 3. Конвертация в пары для форматирования
    aligned_pairs = [(pair['ru'], pair['zh']) for pair in alignments]

    # 4. ФОРМАТИРОВАНИЕ В HTML
    content_html = BilingualTextAligner.format_for_epub(
        aligned_pairs,
        mode='sentence',
        style='alternating'
    )

    # 5. Создание HTML страницы
    chapter_content = f"""
    <h2 class="chapter-title">{formatted_title}</h2>
    {content_html}
    """
```

### 2. Форматирование текста

**Файл**: `app/utils/text_alignment.py`

#### Метод `format_for_epub()` (строки 145-182)

```python
def format_for_epub(aligned_pairs: List[Tuple[str, str]],
                   mode='sentence',
                   style='alternating') -> str:
    """Форматирует пары RU/ZH в HTML"""

    if style == 'alternating':
        html_parts = []
        for ru, zh in aligned_pairs:
            if ru:
                html_parts.append(f'<p class="russian-sentence">{ru}</p>')
            if zh:
                # ← ЗДЕСЬ НУЖНО ВЫДЕЛЯТЬ ТЕРМИНЫ!
                html_parts.append(f'<p class="chinese-sentence">{zh}</p>')
        return '\n'.join(html_parts)
```

**Текущий вывод**:
```html
<p class="russian-sentence">Линь Дун вышел из пещеры.</p>
<p class="chinese-sentence">林动从洞穴走了出来。</p>
```

**Желаемый вывод** (с выделением терминов):
```html
<p class="russian-sentence">Линь Дун вышел из пещеры.</p>
<p class="chinese-sentence"><strong>林动</strong>从洞穴走了出来。</p>
                        ↑ выделено жирным (термин из глоссария)
```

### 3. Глоссарий

**Файл**: `app/models/glossary.py`

#### Модель `GlossaryItem` (строки 7-84)

```python
class GlossaryItem(db.Model):
    __tablename__ = 'glossary_items'

    id = Column(Integer, primary_key=True)
    novel_id = Column(Integer, ForeignKey('novels.id'))

    # Термины
    english_term = Column(String(255))  # "Lin Dong", "Nirvana Tribulation"
    russian_term = Column(String(255))  # "Линь Дун", "Нирвана"

    # Категории
    category = Column(String(50))  # character, location, term, technique, artifact

    # Дополнительно
    description = Column(Text)
    first_appearance_chapter = Column(Integer)
    usage_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
```

**Особенность**: Китайские термины УЖЕ ЕСТЬ в поле `english_term`!
- Поле `english_term` → **фактически содержит китайские иероглифы** (李楊, 星羅, etc.)
- Поле `russian_term` → русский перевод (Ли Ян, Синло, etc.)
- **Название поля неудачное**, но данные есть!

### 4. Структура BilingualAlignment

**Файл**: `app/services/bilingual_alignment_service.py`

#### Результат `align_chapter()` (строки 39-285)

```python
return [
    {
        "ru": "Линь Дун вышел из пещеры.",
        "zh": "林动从洞穴走了出来。",
        "type": "description",
        "confidence": 0.95
    },
    # ... другие пары ...
]
```

**Что есть**: Сопоставленные пары русского и китайского текста
**Чего нет**: Информации о терминах глоссария

## Проблемы и решения

### ✅ Решена: Китайские термины уже есть!

**Фактическая структура**:
```python
GlossaryItem:
    english_term = "李楊"      # ← фактически китайские иероглифы!
    russian_term = "Ли Ян"     # ← русский перевод
```

**Почему так получилось**:
- Поле названо `english_term`, но содержит китайские иероглифы
- Это legacy название, данные уже корректные
- Пример из БД (novel_id=21):
  - `english_term = "李楊"` → `russian_term = "Ли Ян"`
  - `english_term = "星羅"` → `russian_term = "Синло"`

**Что нужно сделать**:
1. ✅ Добавить метод `get_chinese_terms_dict()` → **УЖЕ СДЕЛАНО** (glossary.py:66-94)
2. ✅ Использовать `item.english_term` как китайский термин
3. ⚠️ Опционально: переименовать поле для ясности (можно отложить)

### Проблема 2: Поиск терминов в тексте

Даже если есть китайские термины, нужно найти их в тексте:

```python
chinese_text = "林动从洞穴走了出来，看向天空。"
terms = ["林动", "天空"]  # Термины из глоссария

# Нужно найти позиции терминов в тексте
# Результат: [("林动", 0, 2), ("天空", 13, 15)]
```

**Проблемы**:
- Перекрывающиеся термины: "涅槃" vs "涅槃劫" (оба в глоссарии)
- Частичные совпадения: "林" (фамилия) vs "林动" (полное имя)
- Порядок приоритета: длинные термины должны иметь приоритет

## Предлагаемое решение

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Расширение модели GlossaryItem                          │
│    + chinese_term: String(255)                              │
│    + Миграция БД                                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Новый класс GlossaryHighlighter                         │
│    - highlight_terms_in_text(text, terms)                   │
│    - find_used_terms(text, terms)                           │
│    - format_glossary_section(terms)                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Модификация format_for_epub()                           │
│    - Добавить параметр glossary_items                       │
│    - Для каждого zh текста:                                 │
│      * Найти термины                                        │
│      * Выделить жирным                                       │
│      * Сохранить список использованных терминов             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Модификация _create_bilingual_chapter_page()            │
│    - Загрузить глоссарий для novel_id                       │
│    - Передать в format_for_epub()                           │
│    - Добавить секцию терминов в конец главы                 │
└─────────────────────────────────────────────────────────────┘
```

### Детальный план реализации

#### ✅ Этап 1: Метод get_chinese_terms_dict() - ГОТОВ

**Файл**: `app/models/glossary.py` (строки 66-94)

```python
@classmethod
def get_chinese_terms_dict(cls, novel_id):
    """
    Получить словарь: китайский_термин → (русский, описание, категория)

    Примечание: В поле english_term фактически хранятся китайские иероглифы

    Returns:
        {
            "李楊": {
                "russian": "Ли Ян",
                "description": "...",
                "category": "characters"
            },
            ...
        }
    """
    items = cls.query.filter_by(novel_id=novel_id, is_active=True).all()
    result = {}

    for item in items:
        if item.english_term:  # Фактически это китайский термин
            result[item.english_term] = {
                'russian': item.russian_term,
                'description': item.description or '',
                'category': item.category
            }

    return result
```

**Статус**: ✅ **РЕАЛИЗОВАНО** - метод добавлен в модель

#### Этап 2: Создание GlossaryHighlighter

**Новый файл**: `app/utils/glossary_highlighter.py`

```python
"""
Утилиты для выделения терминов глоссария в тексте
"""
import re
from typing import List, Dict, Tuple, Set


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
            glossary_dict: Словарь терминов {chinese_term: {russian, english, ...}}
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

        # Сортируем термины по длине (от длинных к коротким)
        # Это предотвращает частичные совпадения
        # Например: "涅槃劫" должно выделяться раньше чем "涅槃"
        terms = sorted(glossary_dict.keys(), key=len, reverse=True)

        used_terms = set()
        highlighted_text = text

        # Словарь для отслеживания уже замененных позиций
        # Чтобы не заменять термины внутри уже выделенного текста
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
                    # Заменяем в highlighted_text (с учетом смещения от предыдущих замен)
                    # Используем placeholder для безопасной замены
                    placeholder = f"<<<TERM_{len(used_terms)}>>>"
                    highlighted_text = highlighted_text.replace(term, placeholder, 1)

                    # Добавляем термин в использованные
                    used_terms.add(term)

                    # Отмечаем диапазон как замененный
                    replaced_ranges.append((start, end))

        # Заменяем placeholders на финальные теги
        for i, term in enumerate(used_terms):
            placeholder = f"<<<TERM_{i}>>>"
            highlighted_text = highlighted_text.replace(
                placeholder,
                f"<{tag}>{term}</{tag}>"
            )

        return highlighted_text, used_terms

    @staticmethod
    def format_glossary_section(
        used_terms: Set[str],
        glossary_dict: Dict[str, Dict],
        title: str = "Термины в этой главе"
    ) -> str:
        """
        Форматирует секцию с терминами для добавления в конец главы

        Args:
            used_terms: Множество использованных китайских терминов
            glossary_dict: Полный словарь глоссария
            title: Заголовок секции

        Returns:
            HTML-строка с форматированным списком терминов

        Пример вывода:
            <div class="glossary-section">
                <h3>Термины в этой главе</h3>
                <dl class="glossary-list">
                    <dt class="glossary-term-zh">林动</dt>
                    <dd class="glossary-term-ru">Линь Дун (Lin Dong)</dd>
                    <dd class="glossary-term-desc">Главный герой...</dd>
                </dl>
            </div>
        """
        if not used_terms:
            return ""

        # Группируем термины по категориям
        by_category = {
            'character': [],
            'location': [],
            'technique': [],
            'artifact': [],
            'term': []
        }

        for term in sorted(used_terms):
            if term in glossary_dict:
                info = glossary_dict[term]
                category = info.get('category', 'term')

                if category in by_category:
                    by_category[category].append((term, info))

        # Русские названия категорий
        category_names = {
            'character': '👤 Персонажи',
            'location': '📍 Места',
            'technique': '⚔️ Техники',
            'artifact': '🔮 Артефакты',
            'term': '📖 Термины'
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
                en_term = info.get('english', '')
                description = info.get('description', '')

                # Термин на китайском
                html_parts.append(f'<dt class="glossary-term-zh">{zh_term}</dt>')

                # Перевод
                translation = f"{ru_term}"
                if en_term:
                    translation += f" ({en_term})"
                html_parts.append(f'<dd class="glossary-term-ru">{translation}</dd>')

                # Описание (если есть)
                if description:
                    html_parts.append(f'<dd class="glossary-term-desc">{description}</dd>')

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
```

#### Этап 3: Модификация BilingualTextAligner

**Файл**: `app/utils/text_alignment.py`

```python
class BilingualTextAligner:
    # ... существующие методы ...

    @staticmethod
    def format_for_epub(
        aligned_pairs: List[Tuple[str, str]],
        mode: str = 'sentence',
        style: str = 'alternating',
        glossary_dict: Dict[str, Dict] = None,  # НОВЫЙ ПАРАМЕТР
        include_glossary_section: bool = True   # НОВЫЙ ПАРАМЕТР
    ) -> Tuple[str, Set[str]]:  # ИЗМЕНЕН RETURN TYPE!
        """
        Форматирует выравненные пары для EPUB с выделением терминов глоссария

        Args:
            aligned_pairs: Список пар (русский, китайский)
            mode: 'sentence' или 'paragraph'
            style: 'alternating' или 'parallel'
            glossary_dict: Словарь терминов глоссария (новое!)
            include_glossary_section: Включать ли секцию терминов (новое!)

        Returns:
            (html_content, used_terms_set) - кортеж вместо просто строки
        """
        from app.utils.glossary_highlighter import GlossaryHighlighter

        # Если есть глоссарий, обрабатываем термины
        if glossary_dict:
            aligned_pairs, used_terms = GlossaryHighlighter.process_aligned_pairs(
                aligned_pairs, glossary_dict
            )
        else:
            used_terms = set()

        if style == 'alternating':
            html_parts = []
            for ru, zh in aligned_pairs:
                if ru:
                    html_parts.append(f'<p class="russian-sentence">{ru}</p>')
                if zh:
                    # zh уже содержит <strong> теги!
                    html_parts.append(f'<p class="chinese-sentence">{zh}</p>')

            content_html = '\n'.join(html_parts)

            # Добавляем секцию терминов в конец
            if include_glossary_section and used_terms and glossary_dict:
                glossary_section = GlossaryHighlighter.format_glossary_section(
                    used_terms, glossary_dict
                )
                content_html += '\n' + glossary_section

            return content_html, used_terms

        elif style == 'parallel':
            # Аналогично для параллельного стиля
            # ...
            pass
```

#### Этап 4: Модификация EPUBService

**Файл**: `app/services/epub_service.py`

##### 4.1. Обновить CSS стили

```python
def _get_bilingual_css_styles(self) -> str:
    """CSS стили для двуязычного EPUB"""
    return """
    /* ... существующие стили ... */

    /* НОВЫЕ СТИЛИ ДЛЯ ГЛОССАРИЯ */

    .glossary-section {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1.5em;
        margin: 2em 0;
        font-size: 0.95em;
    }

    .glossary-section h3 {
        font-size: 1.2em;
        color: #2c3e50;
        margin: 0 0 1em 0;
        text-align: center;
        border-bottom: 2px solid #3498db;
        padding-bottom: 0.5em;
    }

    .glossary-category {
        font-size: 1.05em;
        color: #34495e;
        margin: 1.2em 0 0.5em 0;
        font-weight: bold;
    }

    .glossary-list {
        margin: 0.5em 0 1em 2em;
    }

    .glossary-term-zh {
        font-family: "Noto Serif CJK SC", "Source Han Serif SC", "SimSun", serif;
        font-size: 1.1em;
        font-weight: bold;
        color: #2c3e50;
        margin-top: 0.8em;
    }

    .glossary-term-ru {
        font-family: "Times New Roman", "Georgia", serif;
        color: #555;
        margin: 0.2em 0 0.2em 1.5em;
    }

    .glossary-term-desc {
        font-size: 0.9em;
        font-style: italic;
        color: #666;
        margin: 0.2em 0 0.5em 1.5em;
    }

    /* Выделение терминов в тексте */
    .chinese-sentence strong {
        color: #c0392b;
        font-weight: bold;
        background-color: #ffe6e6;
        padding: 0 0.2em;
        border-radius: 2px;
    }
    """
```

##### 4.2. Модифицировать `_create_bilingual_chapter_page()`

```python
def _create_bilingual_chapter_page(self, chapter: Dict, nav_css, novel_id: int):
    """Создание страницы главы с двуязычным содержимым и терминами глоссария"""
    from app.models import GlossaryItem

    # ... существующий код получения главы ...

    # НОВОЕ: Загрузка глоссария для новеллы
    glossary_dict = GlossaryItem.get_chinese_terms_dict(novel_id)

    logger.info(f"📖 Создание двуязычной главы {chapter['number']}: "
                f"глоссарий загружен ({len(glossary_dict)} терминов)")

    if db_chapter and db_chapter.original_text:
        # LLM выравнивание
        alignment_service = BilingualAlignmentService()
        alignments = alignment_service.align_chapter(...)
        aligned_pairs = [(pair['ru'], pair['zh']) for pair in alignments]

        # МОДИФИЦИРОВАНО: Передаем глоссарий в format_for_epub
        content_html, used_terms = BilingualTextAligner.format_for_epub(
            aligned_pairs,
            mode='sentence',
            style='alternating',
            glossary_dict=glossary_dict,        # НОВОЕ!
            include_glossary_section=True       # НОВОЕ!
        )

        logger.info(f"   Использовано терминов: {len(used_terms)}")
    else:
        content_html = f'<p class="russian-sentence">{chapter["content"]}</p>'

    # ... остальной код создания страницы ...
```

## Примеры вывода

### Пример 1: Простой текст с терминами

**Входные данные**:
```python
aligned_pairs = [
    ("Линь Дун вышел из пещеры.", "林动从洞穴走了出来。"),
    ("Он посмотрел на небо.", "他看向天空。")
]

glossary_dict = {
    "林动": {
        "russian": "Линь Дун",
        "english": "Lin Dong",
        "description": "Главный герой романа",
        "category": "character"
    }
}
```

**Вывод HTML**:
```html
<p class="russian-sentence">Линь Дун вышел из пещеры.</p>
<p class="chinese-sentence"><strong>林动</strong>从洞穴走了出来。</p>
<p class="russian-sentence">Он посмотрел на небо.</p>
<p class="chinese-sentence">他看向天空。</p>

<div class="glossary-section">
    <h3>Термины в этой главе</h3>
    <h4 class="glossary-category">👤 Персонажи</h4>
    <dl class="glossary-list">
        <dt class="glossary-term-zh">林动</dt>
        <dd class="glossary-term-ru">Линь Дун (Lin Dong)</dd>
        <dd class="glossary-term-desc">Главный герой романа</dd>
    </dl>
</div>
```

### Пример 2: Текст с множеством терминов

**Входные данные**:
```python
aligned_pairs = [
    ("Линь Дун начал культивировать Великую Технику Нирваны.",
     "林动开始修炼大涅槃术。")
]

glossary_dict = {
    "林动": {"russian": "Линь Дун", "english": "Lin Dong", "category": "character"},
    "大涅槃术": {"russian": "Великая Техника Нирваны", "english": "Great Nirvana Art", "category": "technique"},
    "涅槃": {"russian": "Нирвана", "english": "Nirvana", "category": "term"}
}
```

**Вывод** (с правильным приоритетом длинных терминов):
```html
<p class="russian-sentence">Линь Дун начал культивировать Великую Технику Нирваны.</p>
<p class="chinese-sentence"><strong>林动</strong>开始修炼<strong>大涅槃术</strong>。</p>
                            ↑                    ↑ выделен весь термин "大涅槃术"
                                                   а не "涅槃" отдельно!

<div class="glossary-section">
    <h3>Термины в этой главе</h3>
    <h4>👤 Персонажи</h4>
    <dl>
        <dt>林动</dt>
        <dd>Линь Дун (Lin Dong)</dd>
    </dl>
    <h4>⚔️ Техники</h4>
    <dl>
        <dt>大涅槃术</dt>
        <dd>Великая Техника Нирваны (Great Nirvana Art)</dd>
    </dl>
</div>
```

## Проблемы и решения

### Проблема 1: Перекрывающиеся термины

**Пример**:
- Глоссарий: `["涅槃", "涅槃劫", "大涅槃术"]`
- Текст: `"他修炼大涅槃术已经三年了"`

**Решение**: Сортировка терминов по длине (от длинных к коротким)
```python
terms = sorted(glossary_dict.keys(), key=len, reverse=True)
# Результат: ["大涅槃术", "涅槃劫", "涅槃"]
# Сначала выделится "大涅槃术", "涅槃" внутри не будет выделен
```

### Проблема 2: Частичные совпадения

**Пример**:
- Глоссарий: `["林"]` (фамилия)
- Текст: `"林动从森林走出来"`  (林动 - имя, 森林 - лес)

**Решение**: Отслеживание замененных диапазонов
```python
replaced_ranges = []
# При замене "林动" добавляем диапазон (0, 2)
# При попытке заменить "林" проверяем пересечение
# Позиция 0 уже в диапазоне → пропускаем
```

### Проблема 3: Производительность для больших глоссариев

**Сценарий**: Глоссарий 1000+ терминов, текст 5000 иероглифов

**Оптимизация**:
```python
# Вместо перебора всех терминов, сначала фильтруем
def prefilter_terms(text: str, all_terms: List[str]) -> List[str]:
    """Оставляет только термины, которые точно есть в тексте"""
    return [term for term in all_terms if term in text]

terms = prefilter_terms(text, glossary_dict.keys())
# Теперь обрабатываем только релевантные термины
```

### Проблема 4: HTML-экранирование

**Проблема**: Если в тексте есть HTML символы (`<`, `>`, `&`)

**Решение**: Экранирование перед выделением
```python
import html

def highlight_terms_in_text(text, glossary_dict, tag='strong'):
    # Сначала экранируем HTML
    text = html.escape(text)

    # Затем выделяем термины
    # ...

    return highlighted_text
```

## План тестирования

### Unit тесты для GlossaryHighlighter

```python
def test_highlight_single_term():
    text = "林动从洞穴走了出来。"
    glossary = {"林动": {"russian": "Линь Дун", "category": "character"}}

    result, used = GlossaryHighlighter.highlight_terms_in_text(text, glossary)

    assert result == "<strong>林动</strong>从洞穴走了出来。"
    assert used == {"林动"}

def test_highlight_overlapping_terms():
    text = "他修炼大涅槃术。"
    glossary = {
        "涅槃": {"russian": "Нирвана"},
        "大涅槃术": {"russian": "Великая Техника Нирваны"}
    }

    result, used = GlossaryHighlighter.highlight_terms_in_text(text, glossary)

    # Должен выделиться только "大涅槃术", не "涅槃" внутри
    assert result == "他修炼<strong>大涅槃术</strong>。"
    assert used == {"大涅槃术"}

def test_format_glossary_section():
    used_terms = {"林动", "大涅槃术"}
    glossary = {
        "林动": {
            "russian": "Линь Дун",
            "english": "Lin Dong",
            "description": "Главный герой",
            "category": "character"
        },
        "大涅槃术": {
            "russian": "Великая Техника Нирваны",
            "category": "technique"
        }
    }

    html = GlossaryHighlighter.format_glossary_section(used_terms, glossary)

    assert "Термины в этой главе" in html
    assert "👤 Персонажи" in html
    assert "⚔️ Техники" in html
    assert "林动" in html
    assert "Линь Дун" in html
```

### Integration тест для EPUB

```python
def test_bilingual_epub_with_glossary(app, db):
    # 1. Создать новеллу
    novel = Novel(title="Test Novel")
    db.session.add(novel)

    # 2. Добавить главу
    chapter = Chapter(
        novel_id=novel.id,
        chapter_number=1,
        original_text="林动从洞穴走了出来。",
        # ... перевод ...
    )
    db.session.add(chapter)

    # 3. Добавить термины глоссария
    term = GlossaryItem(
        novel_id=novel.id,
        chinese_term="林动",
        russian_term="Линь Дун",
        english_term="Lin Dong",
        category="character"
    )
    db.session.add(term)
    db.session.commit()

    # 4. Генерация EPUB
    epub_service = EPUBService(app)
    chapters = epub_service.get_edited_chapters_from_db(novel.id)
    epub_path = epub_service.create_bilingual_epub(novel.id, chapters)

    # 5. Проверка содержимого EPUB
    book = epub.read_epub(epub_path)
    chapter_content = None

    for item in book.get_items():
        if 'chapter_001' in item.file_name:
            chapter_content = item.content.decode('utf-8')
            break

    # Проверяем выделение термина
    assert '<strong>林动</strong>' in chapter_content

    # Проверяем секцию терминов
    assert 'glossary-section' in chapter_content
    assert '林动' in chapter_content
    assert 'Линь Дун' in chapter_content
```

## ✅ Миграция НЕ требуется

Китайские термины УЖЕ ЕСТЬ в поле `english_term` (строка 15 в glossary.py).

**Проверка**:
```sql
SELECT english, russian, category FROM glossary_items WHERE novel_id = 21 LIMIT 5;

-- Результат:
-- english  | russian                | category
-- ---------|------------------------|----------
-- 李楊     | Ли Ян                  | characters
-- 星羅     | Синло                  | locations
-- 星極三境 | Три обители Звёздного  | terms
```

**Вывод**: Данные готовы к использованию, дополнительная миграция не нужна.

## Дополнительные улучшения

### 1. Частотная аналитика терминов

```python
class GlossaryItem(db.Model):
    # ... существующие поля ...

    # НОВОЕ: JSON поле для статистики по главам
    chapter_usage = Column(JSON)  # {"1": 5, "2": 3, ...} - сколько раз в какой главе

    def increment_chapter_usage(self, chapter_number: int):
        """Увеличивает счетчик использования в конкретной главе"""
        if not self.chapter_usage:
            self.chapter_usage = {}

        chapter_key = str(chapter_number)
        self.chapter_usage[chapter_key] = self.chapter_usage.get(chapter_key, 0) + 1
        self.usage_count += 1
```

### 2. Hover подсказки в EPUB (для продвинутых ридеров)

```html
<p class="chinese-sentence">
    <abbr title="Линь Дун (Lin Dong) - Главный герой">
        <strong>林动</strong>
    </abbr>
    从洞穴走了出来。
</p>
```

**CSS**:
```css
.chinese-sentence abbr {
    text-decoration: none;
    border-bottom: 1px dotted #999;
}

.chinese-sentence abbr:hover {
    cursor: help;
}
```

### 3. Экспорт списка терминов главы в отдельный файл

Для каждой главы создавать дополнительный файл `chapter_001_glossary.xhtml` с полным списком терминов.

### 4. Интерактивный индекс терминов

Добавить в конец EPUB общий индекс всех терминов со ссылками на главы:

```html
<h2>Индекс терминов</h2>
<dl>
    <dt>林动 (Линь Дун)</dt>
    <dd>Главы: <a href="chapter_001.xhtml">1</a>, <a href="chapter_002.xhtml">2</a>, ...</dd>
</dl>
```

## Резюме

### Ключевые изменения

| Компонент | Изменения |
|-----------|-----------|
| **GlossaryItem** | + метод `get_chinese_terms_dict()` ✅ |
| **GlossaryHighlighter** | Новый класс для выделения терминов |
| **BilingualTextAligner** | + параметры `glossary_dict`, `include_glossary_section` |
| **EPUBService** | Передача глоссария в форматирование |
| **CSS стили** | Стили для `.glossary-section` и `strong` в китайском тексте |

### Этапы реализации

1. ✅ **Анализ структуры** (завершено)
2. ✅ **Метод get_chinese_terms_dict()** - добавлен в GlossaryItem (glossary.py:66-94)
3. ⏳ **GlossaryHighlighter** - новый класс (app/utils/glossary_highlighter.py)
4. ⏳ **Модификация форматирования** - обновить `format_for_epub()`
5. ⏳ **CSS стили** - добавить стили глоссария
6. ⏳ **Интеграция в EPUB** - обновить `_create_bilingual_chapter_page()`
7. ⏳ **Тестирование** - unit и integration тесты

### Оценка времени

- ~~Миграция БД: 30 минут~~ → ✅ НЕ НУЖНА (данные уже есть)
- ~~Метод get_chinese_terms_dict(): 30 минут~~ → ✅ ГОТОВО
- GlossaryHighlighter: 2-3 часа
- Модификация форматирования: 1-2 часа
- CSS и интеграция: 1 час
- Тестирование: 2-3 часа
- ~~Миграция данных: 1-2 часа~~ → ✅ НЕ НУЖНА (данные уже есть)

**Итого**: 6-9 часов разработки (вместо 8-12)

### Риски

| Риск | Вероятность | Решение |
|------|-------------|---------|
| Перекрывающиеся термины | Высокая | Сортировка по длине |
| Производительность для больших глоссариев | Средняя | Префильтрация терминов |
| ~~Отсутствие китайских терминов в БД~~ | ~~Высокая~~ | ✅ Данные уже есть |
| HTML-экранирование | Низкая | `html.escape()` |

---

**Статус**: 📋 Подробный анализ и план готовы
**Следующий шаг**: Согласование с заказчиком и начало реализации
