# Структура базы данных для билингвального выравнивания

## Обзор системы

Система билингвального выравнивания предназначена для автоматического сопоставления китайского оригинала и русского перевода глав новелл с использованием LLM моделей. Результаты выравнивания кэшируются в БД для быстрого доступа и отображения в двуязычном EPUB.

### Основные компоненты:
1. **Шаблоны промптов** (`bilingual_prompt_templates`) - конфигурация для LLM выравнивания
2. **Результаты выравнивания** (`bilingual_alignments`) - кэш выравненных пар текстов
3. **Связи** с AI моделями, главами, новеллами

---

## 1. Таблица `bilingual_prompt_templates`

Хранит шаблоны промптов для LLM выравнивания текстов.

### Структура (20 колонок):

```sql
CREATE TABLE bilingual_prompt_templates (
    -- Идентификация
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(200) NOT NULL UNIQUE,
    category            VARCHAR(100),                    -- Категория: 'xianxia', 'wuxia', 'general'

    -- Промпты для LLM
    system_prompt       TEXT,                            -- System prompt для модели
    alignment_prompt    TEXT NOT NULL,                   -- User prompt с плейсхолдерами {russian_text}, {chinese_text}

    -- Параметры LLM
    default_model_id    INTEGER REFERENCES ai_models(id), -- AI модель по умолчанию (NEW!)
    temperature         DOUBLE PRECISION DEFAULT 0.3,    -- Температура генерации
    max_tokens          INTEGER DEFAULT 8000,            -- Макс. токенов в ответе

    -- Настройки качества
    min_quality_threshold DOUBLE PRECISION DEFAULT 0.8,  -- Минимальный порог качества

    -- Метаданные
    description         TEXT,                            -- Описание шаблона
    is_default          BOOLEAN DEFAULT FALSE,           -- Использовать по умолчанию
    is_active           BOOLEAN DEFAULT TRUE,            -- Активен ли шаблон

    -- Использование
    usage_count         INTEGER DEFAULT 0,               -- Счётчик использований
    success_rate        DOUBLE PRECISION,                -- Процент успешных выравниваний
    avg_quality         DOUBLE PRECISION,                -- Средняя оценка качества

    -- Автор и управление
    created_by          VARCHAR(100),                    -- Кто создал
    is_system           BOOLEAN DEFAULT FALSE,           -- Системный шаблон

    -- Временные метки
    created_at          TIMESTAMP,
    updated_at          TIMESTAMP
);
```

### Связи:
- `default_model_id` → `ai_models.id` (FK) - AI модель для выравнивания
- **Обратная связь**: `novels.bilingual_template_id` → `bilingual_prompt_templates.id`
- **Обратная связь**: `bilingual_alignments.template_used_id` → `bilingual_prompt_templates.id`

### Пример данных:

| id | name | category | default_model_id | temperature | max_tokens | is_default | is_active |
|----|------|----------|------------------|-------------|------------|------------|-----------|
| 1 | Default Bilingual Template | general | 16 | 0.30 | 8000 | true | true |
| 2 | Xianxia Bilingual | xianxia | 16 | 0.30 | 8000 | false | true |

**Модель 16**: Qwen3-VL (provider: ollama)

### Использование в коде:

```python
# Получение шаблона для новеллы
template = novel.bilingual_template or BilingualPromptTemplateService.get_default_template()

# Использование модели из шаблона
model_id = template.default_model_id  # Приоритет: шаблон → сервис → None
```

---

## 2. Таблица `bilingual_alignments`

Кэш результатов LLM выравнивания для глав.

### Структура (17 колонок):

```sql
CREATE TABLE bilingual_alignments (
    -- Идентификация
    id                  SERIAL PRIMARY KEY,
    chapter_id          INTEGER NOT NULL UNIQUE REFERENCES chapters(id),  -- Одно выравнивание на главу

    -- Данные выравнивания
    alignment_data      JSON NOT NULL,                   -- Массив пар {ru, zh, type, confidence}

    -- Метаданные выравнивания
    alignment_method    VARCHAR(50),                     -- 'llm', 'regex_fallback', 'monolingual'
    model_used          VARCHAR(100),                    -- Название использованной модели
    template_used_id    INTEGER REFERENCES bilingual_prompt_templates(id),

    -- Метрики качества
    quality_score       DOUBLE PRECISION,                -- Итоговая оценка качества (0.0-1.0)
    coverage_ru         DOUBLE PRECISION,                -- Покрытие русского текста (0.0-1.0)
    coverage_zh         DOUBLE PRECISION,                -- Покрытие китайского текста (0.0-1.0)
    avg_confidence      DOUBLE PRECISION,                -- Средняя уверенность LLM (0.0-1.0)

    -- Статистика
    total_pairs         INTEGER,                         -- Количество выравненных пар
    misalignment_count  INTEGER,                         -- Пары с низкой уверенностью (<0.7)

    -- Верификация человеком
    verified_by_human   BOOLEAN,                         -- Проверено редактором
    verification_notes  TEXT,                            -- Заметки редактора
    verified_at         TIMESTAMP,

    -- Временные метки
    created_at          TIMESTAMP,
    updated_at          TIMESTAMP
);

-- Индексы
CREATE UNIQUE INDEX ON bilingual_alignments(chapter_id);  -- Одно выравнивание на главу
```

### Связи:
- `chapter_id` → `chapters.id` (FK, UNIQUE) - каждой главе соответствует одно выравнивание
- `template_used_id` → `bilingual_prompt_templates.id` (FK) - какой шаблон использовался

### Computed Properties (в коде):

```python
# В модели BilingualAlignment
@property
def needs_review(self) -> bool:
    """Требует ли проверки (низкое качество или много ошибок)"""
    return (self.quality_score < 0.85 or
            self.misalignment_count > self.total_pairs * 0.1)

@property
def is_high_quality(self) -> bool:
    """Высокое качество выравнивания"""
    return (self.quality_score >= 0.9 and
            self.avg_confidence >= 0.85)
```

### Статистика:

```sql
SELECT
    COUNT(*) as total_alignments,           -- 1 (на текущий момент)
    AVG(quality_score) as avg_quality,      -- 0.96
    AVG(total_pairs) as avg_pairs           -- 32
FROM bilingual_alignments;
```

---

## 3. JSON структура `alignment_data`

Поле `alignment_data` хранит результат LLM выравнивания в формате JSON:

### Схема:

```json
{
  "stats": {
    "total_pairs": 23,        // Общее количество пар
    "ru_sentences": 23,       // Количество русских предложений
    "zh_sentences": 23,       // Количество китайских предложений
    "avg_confidence": 0.96    // Средняя уверенность
  },
  "alignments": [
    {
      "ru": "Русский текст",
      "zh": "中文文本",
      "type": "description",  // Тип: description, dialogue, action, unknown
      "confidence": 0.95      // Уверенность LLM (0.0-1.0)
    },
    // ... остальные пары
  ]
}
```

### Типы пар (`type`):

- **`description`** - описательный текст, повествование
- **`dialogue`** - диалоги и реплики персонажей
- **`action`** - действия, события
- **`unknown`** - тип не определён (regex fallback)

### Пример реальных данных:

```json
{
  "stats": {
    "total_pairs": 23,
    "ru_sentences": 23,
    "zh_sentences": 23,
    "avg_confidence": 0.96
  },
  "alignments": [
    {
      "ru": "Ночь 18 сентября 2013 года, 22:15. Окраина Шанхая.",
      "zh": "2013年的9月18日夜22:15的上海郊區。",
      "type": "description",
      "confidence": 1.0
    },
    {
      "ru": "Ночной Шанхай по-прежнему был таким притягательным — словно прекрасная незнакомка в мерцающем полумраке...",
      "zh": "夜晚的上海依舊是那麽的吸引人，就仿佛處於蒙朧中的美女，讓你想要靠近，想要揭開她那神秘面紗！...",
      "type": "description",
      "confidence": 0.95
    },
    {
      "ru": "— О, какой красавец! И особняк, наверное, стоит почти десять миллионов! Я решила — такого я себе найду!",
      "zh": "啊，好帥啊，這棟別墅似乎也要近千萬的吧！我決定了我以後一定要找一個這樣的男孩！",
      "type": "dialogue",
      "confidence": 0.95
    }
  ]
}
```

---

## 4. Связи с другими таблицами

### Диаграмма связей:

```
novels
  ├─ bilingual_template_id → bilingual_prompt_templates.id
  └─ chapters []
       └─ bilingual_alignments.chapter_id (1:1)
            └─ template_used_id → bilingual_prompt_templates.id

bilingual_prompt_templates
  ├─ default_model_id → ai_models.id
  └─ used_in: bilingual_alignments.template_used_id

ai_models
  └─ used_in: bilingual_prompt_templates.default_model_id
```

### Запрос полной информации:

```sql
SELECT
    ba.id,
    c.chapter_number,
    n.title as novel_title,
    ba.quality_score,
    ba.total_pairs,
    ba.alignment_method,
    ba.model_used,
    t.name as template_name,
    m.name as ai_model_name,
    m.provider as ai_provider
FROM bilingual_alignments ba
JOIN chapters c ON ba.chapter_id = c.id
JOIN novels n ON c.novel_id = n.id
LEFT JOIN bilingual_prompt_templates t ON ba.template_used_id = t.id
LEFT JOIN ai_models m ON t.default_model_id = m.id
WHERE n.id = 21
ORDER BY c.chapter_number;
```

---

## 5. Поток данных при выравнивании

### Процесс создания выравнивания:

```
1. Пользователь нажимает "Загрузить выравнивание" в UI
   ↓
2. API: GET /api/bilingual/<chapter_id>/alignment
   ↓
3. BilingualAlignmentService.align_chapter(chapter)
   │
   ├─ Проверка кэша в bilingual_alignments
   │  └─ Если есть → возврат cached alignment
   │
   ├─ Получение данных
   │  ├─ russian_text (из chapter.edited_translation или current_translation)
   │  └─ chinese_text (из chapter.original_text)
   │
   ├─ Получение шаблона промпта
   │  ├─ Приоритет 1: template_id переданный в сервис
   │  ├─ Приоритет 2: novel.bilingual_template
   │  └─ Приоритет 3: default template (is_default=true)
   │
   ├─ Определение AI модели
   │  ├─ Приоритет 1: model_id переданный в сервис
   │  ├─ Приоритет 2: template.default_model_id
   │  └─ Приоритет 3: None (дефолтная модель)
   │
   ├─ Построение промпта
   │  └─ template.alignment_prompt.format(
   │       russian_text=russian_text,
   │       chinese_text=chinese_text
   │     )
   │
   ├─ LLM запрос через AIAdapterService
   │  └─ asyncio.run(ai_adapter.generate_content(
   │       system_prompt=template.system_prompt,
   │       user_prompt=prompt,
   │       temperature=template.temperature,
   │       max_tokens=template.max_tokens
   │     ))
   │
   ├─ Парсинг JSON ответа
   │  └─ Извлечение {"alignments": [...], "stats": {...}}
   │
   ├─ Валидация качества
   │  ├─ coverage_ru = len(aligned_ru) / len(russian_text)
   │  ├─ coverage_zh = len(aligned_zh) / len(chinese_text)
   │  ├─ avg_confidence = average(pair.confidence)
   │  └─ quality_score = coverage_ru*0.3 + coverage_zh*0.3 + avg_confidence*0.4
   │
   ├─ Если quality_score < 0.8 → fallback regex alignment
   │
   └─ Сохранение в bilingual_alignments
      ├─ chapter_id
      ├─ alignment_data (JSON)
      ├─ alignment_method ('llm')
      ├─ model_used (ai_adapter.model.name)
      ├─ template_used_id
      ├─ quality_score, coverage_ru, coverage_zh, avg_confidence
      ├─ total_pairs
      └─ misalignment_count (пары с confidence < 0.7)
   ↓
4. Возврат alignments в UI
   ↓
5. Отображение в двуязычном превью/EPUB
```

### Процесс пересоздания:

```
1. Пользователь нажимает "Пересоздать выравнивание"
   ↓
2. API: POST /api/bilingual/<chapter_id>/regenerate
   ↓
3. BilingualAlignmentService.regenerate_alignment(chapter)
   ├─ DELETE FROM bilingual_alignments WHERE chapter_id = ?
   └─ align_chapter(chapter, force_refresh=True)
```

---

## 6. Методы выравнивания

### LLM метод (основной):

- **Метод**: `'llm'`
- **Качество**: обычно 0.85-0.98
- **Преимущества**:
  - Точная сегментация
  - Определение типа текста (dialogue/description/action)
  - Высокая confidence
- **Используется**: когда есть chinese_text и russian_text

### Regex Fallback:

- **Метод**: `'regex_fallback'`
- **Качество**: фиксированное 0.5
- **Когда используется**:
  - Ошибка LLM
  - Низкое качество LLM результата (<0.8)
  - Timeout LLM запроса
- **Реализация**: `app/utils/text_alignment.py:BilingualTextAligner.align_sentences()`

### Monolingual (только русский):

- **Метод**: `'monolingual'`
- **Качество**: 1.0
- **Когда используется**: нет chinese_text (только перевод без оригинала)
- **Формат**: разбивка на абзацы, zh пустое

---

## 7. Примеры SQL запросов

### Получить статистику по качеству:

```sql
SELECT
    alignment_method,
    COUNT(*) as count,
    AVG(quality_score)::numeric(5,2) as avg_quality,
    AVG(total_pairs)::int as avg_pairs,
    AVG(misalignment_count)::int as avg_errors
FROM bilingual_alignments
GROUP BY alignment_method;
```

### Найти главы, требующие пересмотра:

```sql
SELECT
    ba.id,
    c.chapter_number,
    n.title,
    ba.quality_score,
    ba.misalignment_count,
    ba.total_pairs
FROM bilingual_alignments ba
JOIN chapters c ON ba.chapter_id = c.id
JOIN novels n ON c.novel_id = n.id
WHERE ba.quality_score < 0.85
   OR ba.misalignment_count > ba.total_pairs * 0.1
ORDER BY ba.quality_score ASC;
```

### Получить выравнивание с метаданными:

```sql
SELECT
    ba.alignment_data->'alignments' as pairs,
    ba.alignment_data->'stats' as stats,
    ba.quality_score,
    t.name as template_name,
    m.name as model_name
FROM bilingual_alignments ba
LEFT JOIN bilingual_prompt_templates t ON ba.template_used_id = t.id
LEFT JOIN ai_models m ON t.default_model_id = m.id
WHERE ba.chapter_id = 23451;
```

### Обновить счётчик использований шаблона:

```sql
UPDATE bilingual_prompt_templates
SET
    usage_count = usage_count + 1,
    avg_quality = (
        SELECT AVG(quality_score)
        FROM bilingual_alignments
        WHERE template_used_id = bilingual_prompt_templates.id
    ),
    success_rate = (
        SELECT
            COUNT(*) FILTER (WHERE quality_score >= 0.8)::float /
            COUNT(*)::float * 100
        FROM bilingual_alignments
        WHERE template_used_id = bilingual_prompt_templates.id
    )
WHERE id = 1;
```

---

## 8. Индексы и производительность

### Существующие индексы:

```sql
-- bilingual_prompt_templates
CREATE UNIQUE INDEX bilingual_prompt_templates_name_key ON bilingual_prompt_templates(name);
CREATE INDEX bilingual_prompt_templates_default_model_id_idx ON bilingual_prompt_templates(default_model_id);

-- bilingual_alignments
CREATE UNIQUE INDEX bilingual_alignments_chapter_id_key ON bilingual_alignments(chapter_id);
CREATE INDEX bilingual_alignments_template_used_id_idx ON bilingual_alignments(template_used_id);
```

### Рекомендуемые дополнительные индексы:

```sql
-- Для поиска по качеству
CREATE INDEX idx_alignments_quality ON bilingual_alignments(quality_score DESC);

-- Для поиска активных шаблонов по категории
CREATE INDEX idx_templates_category_active ON bilingual_prompt_templates(category, is_active)
WHERE is_active = true;

-- Для статистики по новеллам
CREATE INDEX idx_alignments_novel ON bilingual_alignments(chapter_id)
INCLUDE (quality_score, total_pairs);
```

---

## 9. Миграции

### История изменений:

1. **Создание базовых таблиц** (начальная миграция)
   - `bilingual_prompt_templates` (19 колонок)
   - `bilingual_alignments` (17 колонок)

2. **Добавление default_model_id** (миграция `b62aa75200f3`)
   ```python
   def upgrade():
       with op.batch_alter_table('bilingual_prompt_templates') as batch_op:
           batch_op.add_column(sa.Column('default_model_id', sa.Integer(), nullable=True))
           batch_op.create_foreign_key(None, 'ai_models', ['default_model_id'], ['id'])

   def downgrade():
       with op.batch_alter_table('bilingual_prompt_templates') as batch_op:
           batch_op.drop_constraint(None, type_='foreignkey')
           batch_op.drop_column('default_model_id')
   ```

---

## 10. API Endpoints

### Получение выравнивания:

```
GET /api/bilingual/<chapter_id>/alignment
Response: {
    "alignments": [...],
    "stats": {...},
    "quality_score": 0.96,
    "cached": true
}
```

### Пересоздание выравнивания:

```
POST /api/bilingual/<chapter_id>/regenerate
Response: {
    "success": true,
    "alignments": [...],
    "quality_score": 0.96
}
```

### Превью выравнивания:

```
GET /api/bilingual/<chapter_id>/preview
Response: {
    "cached": true,
    "quality_score": 0.96,
    "total_pairs": 32,
    "coverage_ru": 0.98,
    "coverage_zh": 0.97,
    "avg_confidence": 0.96,
    "method": "llm",
    "model_used": "gemini-2.0-flash-exp",
    "needs_review": false,
    "is_high_quality": true,
    "preview_pairs": [первые 5 пар],
    "created_at": "2025-01-16T10:30:00"
}
```

---

## Заключение

Система билингвального выравнивания использует две основные таблицы:

1. **`bilingual_prompt_templates`** - конфигурация LLM промптов с выбором AI модели
2. **`bilingual_alignments`** - кэш результатов выравнивания с метриками качества

Ключевые особенности:
- ✅ Одно выравнивание на главу (UNIQUE constraint)
- ✅ Кэширование результатов в БД
- ✅ Автоматическая валидация качества
- ✅ Fallback методы при ошибках LLM
- ✅ Поддержка нескольких AI моделей через шаблоны
- ✅ JSON структура для гибкого хранения пар
- ✅ Метрики качества и статистика использования
