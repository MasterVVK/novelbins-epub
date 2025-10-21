# Анализ системы редактуры web_app и интеграции глоссария с оригинальным текстом

## Резюме

Проведен детальный анализ приложения web_app с целью улучшения системы редактуры путем интеграции глоссария и оригинального текста. Система уже частично поддерживает работу с глоссарием через `GlossaryAwareEditorService`, но не использует оригинальный текст при редактировании, что снижает качество и точность перевода.

## Текущая архитектура

### 1. Сервисы редактирования

#### 1.1 EditorService (базовый)
- **Файл**: `/web_app/app/services/editor_service.py`
- **Функционал**: Стандартная редактура в 4 этапа
- **Процесс**:
  1. Анализ качества текста (1-10)
  2. Улучшение стиля
  3. Полировка диалогов
  4. Финальная полировка
- **Недостатки**: Не использует глоссарий и оригинальный текст

#### 1.2 GlossaryAwareEditorService (с глоссарием)
- **Файл**: `/web_app/app/services/glossary_aware_editor_service.py`
- **Функционал**: Редактура с учетом глоссария
- **Процесс**:
  1. Загрузка приоритизированного глоссария
  2. Обнаружение несоответствий глоссарию
  3. Исправление несоответствий (первый приоритет!)
  4. Улучшение стиля с сохранением терминов
  5. Полировка диалогов с учетом персонажей
  6. Финальная проверка соответствия
- **Преимущества**:
  - Приоритизация терминов (critical > important > standard)
  - Автоматическое обнаружение и исправление несоответствий
  - +3 к качеству за использование глоссария

#### 1.3 ParallelEditorService (параллельная)
- **Файл**: `/web_app/app/services/parallel_editor_service.py`
- **Функционал**: Параллельная обработка с контекстом
- **Особенности**:
  - Контекст из 5 предыдущих глав
  - Параллельная обработка стиля и диалогов
  - Многопоточность через ThreadPoolExecutor

### 2. Модели данных

#### 2.1 Chapter
```python
- id, novel_id, chapter_number
- original_title    # Заголовок на английском
- original_text     # ОРИГИНАЛЬНЫЙ ТЕКСТ (китайский/английский)
- url              # Источник
- word_count_original, word_count_translated
- status: pending|parsed|translated|edited|error
```

#### 2.2 Translation
```python
- chapter_id
- translated_title, translated_text
- translation_type: initial|edited|final
- api_used, model_used
- quality_score (1-10)
- context_used (JSON с метаданными)
```

#### 2.3 GlossaryItem
```python
- novel_id
- english_term      # Оригинальный термин (китайский)
- russian_term      # Русский перевод
- category: characters|locations|terms|techniques|artifacts
- description
- usage_count
```

## Ключевые находки

### 1. Доступность оригинального текста

✅ **Оригинальный текст ДОСТУПЕН** в модели Chapter через поле `chapter.original_text`

📍 **Где используется**:
- `TranslatorService` - для первичного перевода
- `chapter_detail.html` - отображение в интерфейсе
- `glossary_extractor.py` - извлечение терминов

⚠️ **Где НЕ используется**:
- ❌ `EditorService` - не использует оригинал
- ❌ `GlossaryAwareEditorService` - не использует оригинал
- ❌ `ParallelEditorService` - не использует оригинал

### 2. Проблемы текущей реализации

1. **Потеря контекста**: Редакторы работают только с переведенным текстом, теряя нюансы оригинала
2. **Неточная терминология**: Без оригинала невозможно проверить правильность перевода терминов
3. **Ошибки в именах**: Нельзя сверить имена персонажей с оригиналом
4. **Упущенные детали**: Важные культурные/жанровые элементы могут быть потеряны

### 3. Глоссарий в системе

✅ **Сильные стороны**:
- Приоритизация терминов по важности
- Автоматическое обнаружение несоответствий
- Интеграция в промпты редактора
- CRUD API для управления

⚠️ **Слабые стороны**:
- Глоссарий содержит английские термины вместо китайских
- Нет прямой связи между оригиналом и глоссарием при редактировании
- Отсутствует валидация терминов по оригинальному тексту

## Рекомендации по улучшению

### 1. Интеграция оригинального текста в редактуру

#### 1.1 Модификация GlossaryAwareEditorService

```python
def edit_chapter(self, chapter: Chapter) -> bool:
    # Получаем оригинальный текст
    original_text = chapter.original_text

    # Передаем оригинал в методы редактирования
    edited_text = self.improve_style_with_original(
        translated_text,
        original_text,
        glossary,
        chapter.id
    )
```

#### 1.2 Новые методы с оригиналом

```python
def validate_names_with_original(self, translated: str, original: str, glossary: Dict):
    """Проверка имен персонажей по оригиналу"""

def extract_missing_terms(self, original: str, translated: str):
    """Извлечение упущенных терминов из оригинала"""

def verify_cultural_elements(self, original: str, translated: str):
    """Проверка культурных элементов"""
```

### 2. Улучшенные промпты с оригиналом

#### 2.1 Промпт для исправления терминов
```python
prompt = f"""
ОРИГИНАЛЬНЫЙ ТЕКСТ (для справки):
{original_text[:1000]}

ПЕРЕВЕДЕННЫЙ ТЕКСТ:
{translated_text}

ГЛОССАРИЙ:
{glossary_terms}

ЗАДАЧА:
1. Сверьте все имена и термины с оригиналом
2. Исправьте несоответствия согласно глоссарию
3. Сохраните точность культурных элементов
"""
```

#### 2.2 Промпт для улучшения стиля
```python
prompt = f"""
Улучшите стиль перевода, сверяясь с оригиналом для точности.

ОРИГИНАЛ: {original_excerpt}
ПЕРЕВОД: {translated_text}

Убедитесь что:
- Сохранены все детали оригинала
- Правильно переданы эмоции и тон
- Термины соответствуют глоссарию
"""
```

### 3. Новый сервис: OriginalAwareEditorService

```python
class OriginalAwareEditorService(GlossaryAwareEditorService):
    """Редактор с полной поддержкой оригинала и глоссария"""

    def edit_with_original(self, chapter: Chapter):
        original = chapter.original_text
        translated = chapter.current_translation.translated_text
        glossary = self._load_prioritized_glossary(chapter.novel_id)

        # Этап 1: Сверка с оригиналом
        verified_text = self.verify_against_original(
            original, translated, glossary
        )

        # Этап 2: Извлечение упущенных элементов
        enriched_text = self.enrich_from_original(
            original, verified_text
        )

        # Этап 3: Финальная редактура
        final_text = self.polish_with_context(
            enriched_text, original, glossary
        )
```

### 4. Изменения в UI

#### 4.1 Редактор с параллельным просмотром
```html
<!-- edit_chapter_advanced.html -->
<div class="row">
    <div class="col-md-4">
        <h5>Оригинал</h5>
        <div id="original-text">{{ chapter.original_text }}</div>
    </div>
    <div class="col-md-4">
        <h5>Текущий перевод</h5>
        <textarea id="translated-text">{{ translation.translated_text }}</textarea>
    </div>
    <div class="col-md-4">
        <h5>Глоссарий</h5>
        <div id="glossary-terms">
            {% for term in glossary %}
                <div class="term" data-original="{{ term.english_term }}">
                    {{ term.russian_term }}
                </div>
            {% endfor %}
        </div>
    </div>
</div>
```

#### 4.2 Интерактивная подсветка терминов
```javascript
// Подсветка терминов из глоссария в тексте
function highlightGlossaryTerms() {
    const originalText = document.getElementById('original-text');
    const translatedText = document.getElementById('translated-text');
    const terms = document.querySelectorAll('.term');

    terms.forEach(term => {
        const original = term.dataset.original;
        const translated = term.textContent;

        // Подсветка в оригинале и переводе
        highlightTerm(originalText, original, 'highlight-original');
        highlightTerm(translatedText, translated, 'highlight-translated');
    });
}
```

### 5. API Endpoints для новой функциональности

```python
# /web_app/app/api/editor.py

@api.route('/chapters/<int:chapter_id>/edit-with-original', methods=['POST'])
def edit_chapter_with_original(chapter_id):
    """Редактирование с учетом оригинала и глоссария"""
    chapter = Chapter.query.get_or_404(chapter_id)

    editor = OriginalAwareEditorService(translator_service)
    result = editor.edit_with_original(chapter)

    return jsonify({
        'success': result,
        'original_length': len(chapter.original_text),
        'glossary_terms_used': result.get('glossary_terms_used', 0)
    })

@api.route('/chapters/<int:chapter_id>/validate-terms', methods=['GET'])
def validate_chapter_terms(chapter_id):
    """Валидация терминов по оригиналу"""
    chapter = Chapter.query.get_or_404(chapter_id)

    validator = TermValidator(glossary_service)
    issues = validator.find_term_issues(
        chapter.original_text,
        chapter.current_translation.translated_text
    )

    return jsonify({
        'issues': issues,
        'missing_terms': validator.find_missing_terms()
    })
```

### 6. Поэтапный план внедрения

#### Фаза 1: Подготовка (1-2 дня)
1. ✅ Создать `OriginalAwareEditorService`
2. ✅ Добавить методы работы с оригиналом
3. ✅ Обновить промпты для включения оригинала

#### Фаза 2: Интеграция (2-3 дня)
1. ✅ Модифицировать `GlossaryAwareEditorService`
2. ✅ Добавить API endpoints
3. ✅ Обновить модели для хранения метаданных

#### Фаза 3: UI улучшения (3-4 дня)
1. ✅ Создать расширенный редактор
2. ✅ Добавить параллельный просмотр
3. ✅ Реализовать интерактивную подсветку

#### Фаза 4: Тестирование (2 дня)
1. ✅ Тестирование на реальных главах
2. ✅ Оценка улучшения качества
3. ✅ Оптимизация промптов

### 7. Метрики успеха

- 📈 Повышение quality_score на 2-3 пункта
- ✅ 100% соответствие терминов глоссарию
- 🎯 Снижение ошибок в именах на 90%
- ⚡ Сокращение времени ручной правки на 50%
- 📚 Сохранение всех культурных элементов

## Выводы

Система web_app имеет хорошую базу для редактирования переводов, но не использует весь потенциал доступных данных. Интеграция оригинального текста в процесс редактуры значительно повысит качество и точность переводов.

Рекомендуется начать с создания `OriginalAwareEditorService` и постепенно мигрировать существующую функциональность на новый подход с полной поддержкой оригинала и глоссария.