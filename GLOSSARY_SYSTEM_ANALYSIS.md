# Детальный анализ системы глоссария web_app

## 📊 Текущая архитектура

### База данных
**Таблица `glossary_items`:**
- `novel_id` - привязка к конкретной книге
- `english_term` / `russian_term` - пара перевода
- `category` - классификация (characters, locations, terms, techniques, artifacts)
- `first_appearance_chapter` - первое появление
- `usage_count` - счетчик использования
- `is_auto_generated` - флаг автоматической генерации
- `is_active` - флаг активности

**Статистика по существующим глоссариям:**
- "Я хочу запечатать небеса": 21,803 терминов (1,079 персонажей, 11,760 терминов)
- "В поисках демона": 2,761 термин (650 персонажей, 1,089 терминов)
- "Покрывая Небеса": 17 терминов

### Текущие возможности

#### ✅ Реализовано:
1. **Хранение и управление терминами** - полный CRUD через `GlossaryService`
2. **Категоризация** - 5 категорий с валидацией
3. **Экспорт/импорт** - JSON формат для переноса данных
4. **Оптимизация** - `GlossaryOptimizer` для удаления прямых переводов
5. **Использование при переводе** - интеграция в `TranslatorService`
6. **Извлечение терминов** - через API с промптами
7. **Поиск похожих** - через `SequenceMatcher`
8. **Статистика** - подсчеты и аналитика

#### ❌ Отсутствует:
1. **Прямое копирование между книгами** - нет dedicated метода
2. **Автогенерация из готовых переводов** - только при переводе
3. **Тематические группы** - нет группировки по тематикам
4. **Версионирование** - нет истории изменений
5. **Общий глоссарий** - каждая книга изолирована

## 🎯 Рекомендации по созданию глоссария из переведенных глав

### 1. Автоматическое извлечение терминов

```python
class GlossaryExtractor:
    """Извлечение глоссария из пар оригинал-перевод"""
    
    def extract_from_chapters(self, novel_id: int):
        # 1. Получить все главы с переводами
        chapters = Chapter.query.filter_by(novel_id=novel_id).all()
        
        # 2. Для каждой главы:
        for chapter in chapters:
            original = chapter.original_text
            translation = chapter.get_translation()
            
            # 3. Использовать NLP для выделения:
            # - Имен собственных (NER)
            # - Устойчивых словосочетаний
            # - Повторяющихся специфических терминов
            
            # 4. Сопоставить через позиционное выравнивание
            # или контекстное окно
```

### 2. Интеллектуальное сопоставление

```python
def align_terms(original_text: str, translated_text: str):
    """Выравнивание терминов между языками"""
    
    # Использовать:
    # 1. Частотный анализ - редкие слова чаще являются терминами
    # 2. Контекстное окно - термины появляются в похожем контексте
    # 3. Статистическое выравнивание - TF-IDF, word2vec
    # 4. Правила транслитерации для имен
```

### 3. Тематические глоссарии

```sql
-- Добавить новую таблицу для тематических групп
CREATE TABLE glossary_themes (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,  -- 'ballistics', 'cultivation', 'military'
    description TEXT,
    parent_theme_id INTEGER,  -- для иерархии
    FOREIGN KEY(parent_theme_id) REFERENCES glossary_themes(id)
);

-- Связь терминов с темами
CREATE TABLE glossary_item_themes (
    glossary_item_id INTEGER,
    theme_id INTEGER,
    FOREIGN KEY(glossary_item_id) REFERENCES glossary_items(id),
    FOREIGN KEY(theme_id) REFERENCES glossary_themes(id)
);
```

### 4. Универсальный глоссарий

```python
class UniversalGlossaryService:
    """Глоссарий, общий для всех книг тематики"""
    
    def create_universal_glossary(self, theme: str):
        """Создать общий глоссарий для тематики"""
        # Собрать термины из всех книг темы
        # Дедуплицировать
        # Взвесить по частоте использования
        
    def apply_to_novel(self, novel_id: int, theme: str):
        """Применить тематический глоссарий к книге"""
        # Импортировать релевантные термины
        # Адаптировать под контекст книги
```

## 💡 Пошаговый план реализации

### Фаза 1: Извлечение из существующих переводов
1. **Создать команду CLI для batch-обработки:**
```bash
python manage.py extract-glossary --novel-id 8 --min-frequency 3
```

2. **Реализовать NLP pipeline:**
- Токенизация с сохранением позиций
- NER для имен и названий
- Частотный анализ для терминов
- Контекстное выравнивание

### Фаза 2: Тематическая организация
1. **Расширить БД** для поддержки тем
2. **Создать UI** для управления темами
3. **Реализовать классификатор** терминов по темам

### Фаза 3: Межкнижное переиспользование
1. **API для копирования глоссария:**
```python
@api.route('/glossary/copy/<int:source_novel>/<int:target_novel>')
def copy_glossary(source_novel, target_novel):
    # С фильтрацией по темам и категориям
```

2. **Интеллектуальное слияние:**
- Обнаружение конфликтов
- Приоритизация по качеству
- Сохранение истории

### Фаза 4: Автоматизация
1. **Фоновая задача** для обновления глоссария после перевода
2. **ML-модель** для оценки качества терминов
3. **Рекомендательная система** для новых терминов

## 🔧 Технические детали реализации

### Извлечение терминов из параллельных текстов
```python
import spacy
from collections import Counter
from difflib import SequenceMatcher

class ParallelTextExtractor:
    def __init__(self):
        self.nlp_zh = spacy.load("zh_core_web_sm")  # для китайского
        self.nlp_ru = spacy.load("ru_core_news_sm")  # для русского
    
    def extract_terms(self, original: str, translation: str):
        # 1. Извлечь сущности из оригинала
        doc_zh = self.nlp_zh(original)
        entities_zh = [(ent.text, ent.label_) for ent in doc_zh.ents]
        
        # 2. Извлечь сущности из перевода
        doc_ru = self.nlp_ru(translation)
        entities_ru = [(ent.text, ent.label_) for ent in doc_ru.ents]
        
        # 3. Сопоставить по контексту
        pairs = self.align_by_context(entities_zh, entities_ru)
        
        return pairs
```

### Оптимизация для баллистической тематики
```python
BALLISTICS_KEYWORDS = {
    'en': ['bullet', 'caliber', 'trajectory', 'velocity', 'rifle'],
    'ru': ['пуля', 'калибр', 'траектория', 'скорость', 'винтовка'],
    'zh': ['子弹', '口径', '弹道', '速度', '步枪']
}

def is_ballistics_term(term: str, lang: str) -> bool:
    """Проверка принадлежности к баллистической тематике"""
    keywords = BALLISTICS_KEYWORDS.get(lang, [])
    return any(kw in term.lower() for kw in keywords)
```

## 📈 Ожидаемые результаты

1. **Ускорение перевода** новых книг на 30-40% за счет готового глоссария
2. **Повышение консистентности** терминологии между книгами
3. **Снижение ошибок** при переводе специфических терминов
4. **Экономия API-запросов** за счет кеширования переводов

## 🚀 Быстрый старт

Для немедленного использования существующих глоссариев:

```python
# 1. Экспортировать из книги с хорошим глоссарием
source_glossary = GlossaryService.export_glossary_to_dict(novel_id=7)

# 2. Фильтровать по тематике (например, баллистика)
filtered = filter_by_theme(source_glossary, 'ballistics')

# 3. Импортировать в новую книгу
GlossaryService.import_glossary_from_dict(
    novel_id=new_novel_id,
    glossary_data=filtered
)
```

## Заключение

Система уже имеет солидную основу для работы с глоссариями. Основные направления развития:
1. **Автоматизация извлечения** из готовых переводов
2. **Тематическая организация** для переиспользования
3. **Интеллектуальное сопоставление** терминов
4. **Версионирование и история** изменений

Это позволит создать мощную систему переиспользования знаний между книгами одной тематики.