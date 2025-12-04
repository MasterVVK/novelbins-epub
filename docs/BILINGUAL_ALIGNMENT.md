# Bilingual Alignment System - Полная документация

> Этот файл содержит подробную техническую документацию системы двуязычного сопоставления.
> Краткая справка находится в основном CLAUDE.md.

---

## Bilingual Alignment System Architecture

**Система интеллектуального сопоставления китайского оригинала и русского перевода для создания двуязычных EPUB**

### Overview

Система двуязычного сопоставления использует AI (LLM) для выравнивания китайского оригинала и русского перевода по смыслу, а не по позиции. Это критически важно для качественных двуязычных EPUB, так как:
- Переводы редко соответствуют 1:1 по предложениям
- Порядок фраз может меняться
- Одно китайское предложение может разбиваться на несколько русских и наоборот
- LLM понимает смысловое соответствие текстов

**Ключевое требование**: 100% сохранение текста из обоих языков (оригинала и перевода).

### Data Models

#### BilingualAlignment (`web_app/app/models/bilingual_alignment.py`)

**Основная модель для хранения результатов сопоставления**

```python
class BilingualAlignment(db.Model):
    __tablename__ = 'bilingual_alignments'

    # Основные поля
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), unique=True, nullable=False)

    # Результат сопоставления (JSON массив пар)
    alignment_data = db.Column(db.JSON, nullable=False)
    # Формат: [
    #   {"zh": "中文文本", "ru": "Русский текст", "type": "dialogue", "confidence": 0.95},
    #   {"zh": "...", "ru": "...", "type": "description", "confidence": 0.98}
    # ]

    # Метрики качества
    quality_score = db.Column(db.Float)  # 0.0-1.0, формула: coverage_ru*0.3 + coverage_zh*0.3 + avg_confidence*0.4
    coverage_ru = db.Column(db.Float)    # Покрытие русского текста (0.0-1.0)
    coverage_zh = db.Column(db.Float)    # Покрытие китайского текста (0.0-1.0)
    avg_confidence = db.Column(db.Float) # Средняя уверенность (0.0-1.0)

    # Метаданные
    total_pairs = db.Column(db.Integer)              # Количество сопоставленных пар
    template_id = db.Column(db.Integer, db.ForeignKey('bilingual_prompt_templates.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    chapter = db.relationship('Chapter', backref='bilingual_alignment', uselist=False)
    template = db.relationship('BilingualPromptTemplate', backref='alignments')
```

**Важные особенности**:
- `chapter_id` уникален (один alignment на главу)
- `alignment_data` содержит массив JSON объектов с полями:
  - `zh`: Китайский текст блока
  - `ru`: Русский текст блока
  - `type`: Тип контента (dialogue/description/action/internal/author_note)
  - `confidence`: Уверенность в соответствии (0.0-1.0)
- Качество рассчитывается автоматически при сохранении

#### BilingualPromptTemplate (`web_app/app/models/bilingual_prompt_template.py`)

**Шаблоны промптов для LLM сопоставления**

```python
class BilingualPromptTemplate(db.Model):
    __tablename__ = 'bilingual_prompt_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)

    # Промпты (содержат плейсхолдеры {chinese_text} и {russian_text})
    alignment_prompt = db.Column(db.Text, nullable=False)  # Основной промпт для сопоставления
    system_prompt = db.Column(db.Text)                     # System message для LLM
    validation_prompt = db.Column(db.Text)                 # Промпт для валидации результата
    correction_prompt = db.Column(db.Text)                 # Промпт для исправления ошибок

    # Настройки
    temperature = db.Column(db.Float, default=0.1)         # Низкая для точности
    is_default = db.Column(db.Boolean, default=False)      # Шаблон по умолчанию
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Важно**: Промпты должны требовать от LLM:
1. 100% сохранение текста (главный приоритет)
2. Смысловое соответствие блоков
3. JSON формат ответа с полями `zh`, `ru`, `type`, `confidence`
4. Определение типа контента для каждого блока

#### Расширения моделей Novel и Chapter

**Novel** (`web_app/app/models/novel.py`):
```python
# Новые поля для двуязычного сопоставления
alignment_task_id = db.Column(db.String(255))  # ID активной Celery задачи сопоставления
aligned_chapters = db.Column(db.Integer, default=0)  # Счетчик сопоставленных глав

# Конфигурация
config = {
    'alignment_threads': 3,  # Количество параллельных потоков (1-10, рекомендуется 2-5)
    # ... другие настройки
}
```

**Chapter** (`web_app/app/models/chapter.py`):
```python
# Используется существующий статус 'aligned' для глав с выполненным сопоставлением
# Связь с BilingualAlignment через backref 'bilingual_alignment'
```

### Core Services

#### BilingualAlignmentService (`web_app/app/services/bilingual_alignment_service.py`)

**Основной сервис для AI-powered сопоставления текстов**

**Ключевые методы**:

1. **`align_chapter(chapter: Chapter, template: BilingualPromptTemplate = None) -> BilingualAlignment`** (строки 33-285)
   - Главный метод сопоставления одной главы
   - **Процесс**:
     - Проверка наличия `original_text` (китайский) и edited/translated text (русский)
     - Получение промпт-шаблона (переданный или default)
     - **Прогрессивные попытки с LLM** (3 попытки):
       - Попытка 1: Порог покрытия ≥98%
       - Попытка 2: Порог покрытия ≥96%
       - Попытка 3: Порог покрытия ≥95%
     - Для каждой попытки:
       - Построение промпта через `_build_alignment_prompt()`
       - Запрос к LLM через `ai_adapter`
       - Парсинг JSON ответа через `_parse_llm_response()`
       - **Проверка объема через `_check_volume_integrity()`**
       - Если покрытие < порога → следующая попытка
     - Если все попытки неудачны → **fallback на regex** через `_fallback_regex_alignment()`
     - Валидация результата через `_validate_alignment()`
     - Расчет метрик качества
     - Сохранение в БД
   - **Возвращает**: BilingualAlignment объект

2. **`_build_alignment_prompt(template, russian_text, chinese_text) -> str`** (строки 310-340)
   - Построение промпта с **автоматическим экранированием фигурных скобок**
   - **Процесс экранирования**:
     1. Заменить все `{` → `{{` и `}` → `}}`
     2. Восстановить только `{{chinese_text}}` → `{chinese_text}` и `{{russian_text}}` → `{russian_text}`
     3. Вызвать `.format(chinese_text=..., russian_text=...)`
   - Это решает проблему когда промпт содержит JSON примеры с `{}`

3. **`_parse_llm_response(response: str) -> Dict`** (строки 342-398)
   - Парсинг JSON ответа от LLM с трехуровневой обработкой ошибок
   - **Попытка 1**: Прямой `json.loads()` после удаления markdown блоков
   - **Попытка 2**: Regex извлечение JSON блока `r'\{[\s\S]*?"alignments"[\s\S]*?\][\s\S]*?\}'`
   - **Попытка 3**: Логирование ошибки и выброс исключения
   - Проверяет наличие поля `'alignments'` в результате

4. **`_check_volume_integrity(alignments, russian_text, chinese_text, min_coverage=0.95) -> Tuple[bool, Dict]`** (строки 434-508)
   - **Проверка сохранения 100% текста (игнорируя переносы строк)**
   - **Процесс**:
     - Складывает все `pair['ru']` и `pair['zh']` из alignments
     - **Удаляет переносы строк** из оригинального и сопоставленного текста через `.replace('\n', '')`
     - Вычисляет покрытие: `len(aligned_clean) / len(original_clean)`
     - Проверяет покрытие ≥ `min_coverage` для обоих языков
   - **Возвращает**: `(is_valid: bool, stats: dict)` с детальной статистикой
   - **Статистика включает**:
     - Длины с переносами и без
     - Процент покрытия для каждого языка
     - Количество потерянных символов
     - Количество потерянных переносов строк

5. **`_validate_alignment(alignment_result: Dict) -> bool`** (строки 400-432)
   - Валидация структуры результата
   - Проверки:
     - Наличие поля `'alignments'`
     - Массив не пустой
     - Каждая пара имеет `'zh'`, `'ru'`, `'type'`, `'confidence'`
     - `type` из допустимых значений
     - `confidence` в диапазоне 0.0-1.0

6. **`_fallback_regex_alignment(russian_text: str, chinese_text: str, chapter: Chapter) -> BilingualAlignment`** (строки 510-560)
   - Fallback механизм когда LLM не справляется
   - Использует `BilingualTextAligner.align_sentences()`
   - Простое 1:1 выравнивание по предложениям
   - Фиксированная уверенность 0.5
   - Логирует предупреждение

7. **`_calculate_quality_metrics(alignments: List[Dict], russian_text: str, chinese_text: str) -> Dict`** (строки 562-605)
   - Расчет метрик качества
   - **Формула quality_score**: `coverage_ru * 0.3 + coverage_zh * 0.3 + avg_confidence * 0.4`
   - Покрытие считается **БЕЗ переносов строк**
   - Средняя уверенность = среднее всех `pair['confidence']`

**Дополнительные методы**:
- `get_alignment_by_chapter_id(chapter_id)`: Получение существующего alignment
- `delete_alignment(chapter_id)`: Удаление alignment
- `validate_existing_alignment(alignment_id)`: Повторная валидация

#### BilingualPromptTemplateService (`web_app/app/services/bilingual_prompt_template_service.py`)

**Сервис управления промпт-шаблонами**

**Ключевые методы**:
1. `get_default_template()`: Получение шаблона по умолчанию
2. `create_template(name, description, prompts, settings)`: Создание нового шаблона
3. `update_template(template_id, data)`: Обновление шаблона
4. `delete_template(template_id)`: Удаление шаблона
5. `list_templates(active_only=True)`: Список всех шаблонов
6. `set_default_template(template_id)`: Установка шаблона по умолчанию
7. `validate_template_syntax(template)`: Валидация синтаксиса промпта
8. `test_template(template, sample_texts)`: Тестирование шаблона на примерах
9. `get_template_statistics(template_id)`: Статистика использования шаблона
10. `clone_template(template_id, new_name)`: Клонирование шаблона

#### BilingualTextAligner (`web_app/app/services/bilingual_text_aligner.py`)

**Fallback сервис для regex-based выравнивания**

**Метод**: `align_sentences(russian_text: str, chinese_text: str) -> List[Dict]`
- Разбивает тексты на предложения через регулярки
  - Русский: `.!?` как разделители
  - Китайский: `。！？` как разделители
- Создает простое 1:1 соответствие по позиции
- Определяет тип как 'description' (по умолчанию)
- Уверенность всегда 0.5
- **Используется только когда LLM не справляется**

### Celery Background Tasks

#### align_novel_chapters_task (`web_app/app/celery_tasks.py`, строки 900-1050)

**Фоновая задача массового сопоставления глав новеллы**

**Сигнатура**:
```python
@celery.task(bind=True, name='align_novel_chapters_task')
def align_novel_chapters_task(self, novel_id, chapter_ids=None, parallel_threads=3):
    """
    Массовое сопоставление глав с параллельной обработкой

    Args:
        novel_id: ID новеллы
        chapter_ids: Список ID глав для сопоставления (или None для всех edited)
        parallel_threads: Количество параллельных потоков (1-10)
    """
```

**Процесс выполнения**:

1. **Инициализация** (строки 910-935):
   - Создание Flask `app_context()`
   - Загрузка новеллы и глав
   - Фильтрация глав: `status='edited'` и `original_text != ''`
   - Обновление `novel.alignment_task_id = self.request.id`
   - Настройка `parallel_threads` из `novel.config` или параметра

2. **Защита от дублирования** (строки 936-959):
   ```python
   existing_alignment = BilingualAlignment.query.filter_by(chapter_id=chapter_id).first()

   # Пропускаем только если alignment существует И статус = 'aligned'
   if existing_alignment and chapter.status == 'aligned':
       LogService.log_info(f"✅ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Выравнивание уже существует (пропускаем)")
       continue

   # Если alignment существует, но статус изменен - пересоздаем
   if existing_alignment and chapter.status != 'aligned':
       BilingualAlignment.query.filter_by(chapter_id=chapter_id).delete()
       db.session.commit()
       LogService.log_info(f"🔄 [Novel:{novel_id}, Ch:{chapter.chapter_number}] Статус изменен на '{chapter.status}', пересоздаем сопоставление")
   ```

3. **Параллельная обработка через ThreadPoolExecutor** (строки 960-1020):
   ```python
   from concurrent.futures import ThreadPoolExecutor, as_completed

   def align_single_chapter(chapter_id):
       """Thread-safe функция для сопоставления одной главы"""
       with app.app_context():  # Каждый поток создает свой app_context
           chapter = Chapter.query.get(chapter_id)
           # ... вызов BilingualAlignmentService.align_chapter()
           # ... thread-safe обновление счетчиков через Lock()

   with ThreadPoolExecutor(max_workers=parallel_threads) as executor:
       futures = {executor.submit(align_single_chapter, ch_id): ch_id for ch_id in chapter_ids}
       for future in as_completed(futures):
           # Обработка результатов
   ```

4. **Thread-safe обновления** (строки 990-1010):
   ```python
   from threading import Lock
   counter_lock = Lock()

   with counter_lock:
       processed_count += 1
       success_count += 1
       novel.aligned_chapters = success_count
       db.session.commit()
   ```

5. **Обработка отмены** (строки 1015-1025):
   - Проверка `novel.status == 'alignment_cancelled'` между главами
   - Graceful shutdown при обнаружении отмены
   - Очистка `novel.alignment_task_id`

6. **Финализация** (строки 1030-1050):
   - Установка `novel.status = 'aligned'` при успехе
   - Очистка `novel.alignment_task_id`
   - Логирование финальной статистики

**Отмена задачи через API**:
```python
# web_app/app/api/alignment.py
@alignment_bp.route('/novels/<int:novel_id>/align-chapters/cancel', methods=['POST'])
def cancel_alignment(novel_id):
    novel.status = 'alignment_cancelled'
    celery.control.revoke(novel.alignment_task_id, terminate=True, signal='SIGTERM')
```

### API Endpoints

#### Alignment API (`web_app/app/api/alignment.py`)

**2 основных endpoint'а**:

1. **`POST /api/novels/<id>/align-chapters/cancel`** - Отмена массового сопоставления
2. **`GET /api/alignment/status/<task_id>`** - Статус Celery задачи

#### Bilingual API (`web_app/app/api/bilingual_api.py`)

**12 REST endpoints для полного управления**:

1. `GET /api/bilingual/novels/<id>/alignment` - Все сопоставления новеллы
2. `POST /api/bilingual/chapters/<id>/align` - Сопоставить одну главу
3. `GET /api/bilingual/chapters/<id>/alignment` - Получить сопоставление главы
4. `DELETE /api/bilingual/chapters/<id>/alignment` - Удалить сопоставление
5. `POST /api/bilingual/novels/<id>/align-chapters` - Массовое сопоставление (Celery)
6. `GET /api/bilingual/alignment/<id>` - Детали конкретного alignment
7. `POST /api/bilingual/alignment/<id>/validate` - Повторная валидация
8. `PUT /api/bilingual/alignment/<id>` - Обновить alignment
9. `POST /api/bilingual/templates` - Создать промпт-шаблон
10. `GET /api/bilingual/templates` - Список шаблонов
11. `GET /api/bilingual/templates/<id>` - Детали шаблона
12. `PUT /api/bilingual/templates/<id>` - Обновить шаблон

### Views and Routes

#### Bilingual Views (`web_app/app/views.py`)

**5 основных функций для UI**:

1. `bilingual_alignment_view(novel_id)` - Страница управления сопоставлением новеллы
2. `chapter_alignment_view(chapter_id)` - Просмотр сопоставления одной главы
3. `bilingual_templates_view()` - Управление промпт-шаблонами
4. `create_bilingual_template_view()` - Форма создания шаблона
5. `edit_bilingual_template_view(template_id)` - Редактирование шаблона

### Key Implementation Patterns

#### 1. Прогрессивные пороги покрытия

**Проблема**: LLM иногда теряет часть текста при сопоставлении

**Решение**: 3 попытки с постепенно снижающимися порогами
```python
coverage_thresholds = {
    1: 0.98,  # Попытка 1: требуем 98% покрытия (почти 100%)
    2: 0.96,  # Попытка 2: допускаем 96% (более гибко)
    3: 0.95   # Попытка 3: минимум 95% (приемлемо)
}

for attempt in range(1, max_attempts + 1):
    min_volume_coverage = coverage_thresholds[attempt]
    # ... LLM запрос ...
    volume_valid, stats = self._check_volume_integrity(
        alignments, russian_text, chinese_text, min_coverage=min_volume_coverage
    )
    if volume_valid:
        break  # Успех!
```

**Результат**: Баланс между качеством и 100% сохранением текста

#### 2. Проверка объема БЕЗ переносов строк

**Проблема**: Переносы строк (`\n`) могут отличаться, но это не потеря текста

**Решение**: Удаление `\n` перед сравнением
```python
def _check_volume_integrity(self, alignments, russian_text, chinese_text, min_coverage=0.95):
    # Складываем сопоставленный текст
    aligned_ru_text = ''.join(pair.get('ru', '') for pair in alignments)
    aligned_zh_text = ''.join(pair.get('zh', '') for pair in alignments)

    # УБИРАЕМ ПЕРЕНОСЫ СТРОК для проверки чистого контента
    original_ru_clean = russian_text.replace('\n', '')
    original_zh_clean = chinese_text.replace('\n', '')
    aligned_ru_clean = aligned_ru_text.replace('\n', '')
    aligned_zh_clean = aligned_zh_text.replace('\n', '')

    # Вычисляем покрытие БЕЗ переносов
    coverage_ru = len(aligned_ru_clean) / len(original_ru_clean)
    coverage_zh = len(aligned_zh_clean) / len(original_zh_clean)
```

**Результат**: На реальных данных - 100.00% покрытие (только переносы теряются)

#### 3. Автоматическое экранирование фигурных скобок

**Проблема**: Промпты содержат JSON примеры с `{}`, Python `.format()` пытается их интерпретировать

**Решение**: Двухэтапное экранирование
```python
def _build_alignment_prompt(self, template, russian_text, chinese_text):
    # Шаг 1: Экранируем ВСЕ фигурные скобки
    escaped_template = template.alignment_prompt.replace('{', '{{').replace('}', '}}')

    # Шаг 2: Восстанавливаем ТОЛЬКО наши плейсхолдеры
    escaped_template = escaped_template.replace('{{chinese_text}}', '{chinese_text}')
    escaped_template = escaped_template.replace('{{russian_text}}', '{russian_text}')

    # Шаг 3: Теперь безопасно вызываем format()
    prompt = escaped_template.format(chinese_text=chinese_text, russian_text=russian_text)
    return prompt
```

**Результат**: Промпты могут содержать любые JSON примеры

#### 4. Трехуровневый парсинг JSON

**Проблема**: LLM может вернуть JSON с разным форматированием или в markdown блоке

**Решение**: Каскадный парсинг
```python
def _parse_llm_response(self, response: str) -> Dict:
    # Удаляем markdown
    response = response.strip()
    if response.startswith('```json'): response = response[7:]
    if response.startswith('```'): response = response[3:]
    if response.endswith('```'): response = response[:-3]

    # Попытка 1: Прямой парсинг
    try:
        return json.loads(response)
    except:
        pass

    # Попытка 2: Regex извлечение JSON блока
    pattern = r'\{[\s\S]*?"alignments"[\s\S]*?\][\s\S]*?\}'
    matches = re.findall(pattern, response)
    if matches:
        return json.loads(max(matches, key=len))

    # Попытка 3: Логирование ошибки
    logger.error(f"Не удалось распарсить JSON")
    raise ValueError("Parse failed")
```

**Результат**: Устойчивость к вариациям формата ответа

#### 5. Thread-safe параллельная обработка

**Проблема**: SQLAlchemy сессии не thread-safe

**Решение**: Каждый поток создает свой Flask app_context
```python
def align_single_chapter(chapter_id):
    with app.app_context():  # ← Изолированная сессия БД для потока
        chapter = Chapter.query.get(chapter_id)
        # ... обработка ...

        # Thread-safe обновление счетчиков
        with counter_lock:
            success_count += 1
            novel.aligned_chapters = success_count
            db.session.commit()

with ThreadPoolExecutor(max_workers=parallel_threads) as executor:
    futures = {executor.submit(align_single_chapter, ch_id): ch_id for ch_id in chapter_ids}
```

**Результат**: Безопасная параллельная обработка с PostgreSQL

### Integration with EPUB Generation

**EPUBService интеграция** (`web_app/app/services/epub_service.py`):

При генерации двуязычного EPUB (mode='bilingual'):
1. Загружает `chapter.bilingual_alignment` для каждой главы
2. Если alignment существует:
   - Использует `alignment_data` для точного сопоставления блоков
   - Форматирует как: `[中文] текст` затем `[Русский] текст` для каждой пары
3. Если alignment отсутствует:
   - Fallback: выводит весь китайский текст, затем весь русский
   - Логирует предупреждение

**Преимущества умного сопоставления**:
- Читатель видит смысловое соответствие текстов
- Идеально для изучения языка
- Легко сравнивать оригинал и перевод блок за блоком

### Database Schema

**Таблица `bilingual_alignments`**:
```sql
CREATE TABLE bilingual_alignments (
    id SERIAL PRIMARY KEY,
    chapter_id INTEGER UNIQUE NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    alignment_data JSONB NOT NULL,  -- PostgreSQL JSONB для эффективности
    quality_score REAL,
    coverage_ru REAL,
    coverage_zh REAL,
    avg_confidence REAL,
    total_pairs INTEGER,
    template_id INTEGER REFERENCES bilingual_prompt_templates(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bilingual_alignments_chapter_id ON bilingual_alignments(chapter_id);
CREATE INDEX idx_bilingual_alignments_quality ON bilingual_alignments(quality_score DESC);
```

**Таблица `bilingual_prompt_templates`**:
```sql
CREATE TABLE bilingual_prompt_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    alignment_prompt TEXT NOT NULL,
    system_prompt TEXT,
    validation_prompt TEXT,
    correction_prompt TEXT,
    temperature REAL DEFAULT 0.1,
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Performance Considerations

**Рекомендуемые настройки**:
- **Параллельные потоки**: 2-5 (оптимально 3)
  - Меньше 2: медленно
  - Больше 5: перегрузка AI API и БД
- **Temperature**: 0.1 (низкая для точности)
  - 0.0 дает ХУДШИЕ результаты (слишком консервативно)
  - 0.3+ теряет точность сопоставления

**Оценка времени** (для новеллы 1000 глав):
- **С 3 потоками**: ~15-25 часов
- **LLM запросы**: ~10-20 сек на главу
- **Повторные попытки**: +20-40% времени при потере текста
- **Fallback regex**: мгновенно (но низкое качество)

**Оптимизации**:
- Постоянное хранение результатов в БД (alignment не требует пересоздания)
- Пропуск уже сопоставленных глав (проверка статуса)
- Параллельная обработка через ThreadPoolExecutor
- Использование PostgreSQL JSONB для быстрых запросов по alignment_data

---

---

## Bilingual Alignment Improvements (Session 2024-12)

**Улучшения промпта для сопоставления**:

### Новые типы контента

Добавлены два новых типа для обработки непереведённых блоков:

1. **`author_note`** - авторские заметки, реклама, призывы к подписке
   - Китайский текст без русского соответствия
   - Пример: `{"zh": "求收藏！求推薦！", "ru": "", "type": "author_note", "confidence": 1.0}`

2. **`translator_note`** - примечания переводчика
   - Русский текст без китайского соответствия
   - Пример: `{"zh": "", "ru": "Примечание переводчика", "type": "translator_note", "confidence": 1.0}`

### Промпт-правила (bilingual_prompt_templates)

**Правило 6 - Непереведённые блоки**:
```
Если китайский блок НЕ имеет перевода в русском тексте:
Создавай пару с ПУСТЫМ ru: {"zh": "китайский текст", "ru": "", "type": "author_note", "confidence": 1.0}
Примеры: "求收藏！求推薦！", "兄弟姐妹們...", "UU看書"
```

**Правило 7 - Дополнительный текст в переводе**:
```
Если русский блок НЕ имеет соответствия в китайском оригинале:
Создавай пару с ПУСТЫМ zh: {"zh": "", "ru": "русский текст", "type": "translator_note", "confidence": 1.0}
Примеры: пояснения переводчика, адаптированные фразы
```

### Причины fallback на regex

**Анализ логов показывает три причины fallback**:

1. **Авторские заметки в ZH** (~7% текста):
   - Оригинал содержит рекламу: `兄弟姐妹們，闘別2個月...`, `求收藏！求推薦！`, `UU看書`
   - Не переведено в RU → LLM не включает в результат → покрытие ZH < 95%
   - **Решение**: Правило 6 (author_note с пустым ru)

2. **Дополнительный текст в RU** (~5-10%):
   - Перевод содержит пояснения, отсутствующие в оригинале
   - LLM не может найти соответствие → покрытие RU < 95%
   - **Решение**: Правило 7 (translator_note с пустым zh)

3. **Ошибка парсинга JSON**:
   - LLM возвращает невалидный JSON
   - Retry до 2 раз с задержкой 20 сек
   - **Решение**: Трёхуровневый парсинг (прямой → regex → fallback)

### Диагностика fallback

```sql
-- Найти главы с fallback (quality_score = 0.5)
SELECT c.id, c.chapter_number, ba.quality_score, ba.model_used
FROM bilingual_alignments ba
JOIN chapters c ON ba.chapter_id = c.id
WHERE c.novel_id = 11 AND ba.quality_score = 0.5;

-- Сбросить для пересопоставления
DELETE FROM bilingual_alignments WHERE chapter_id = <id>;
UPDATE chapters SET status = 'edited' WHERE id = <id>;
```

### Логи сопоставления

```bash
# Типичный успешный лог:
[Novel:11, Ch:4] Попытка 1/3 (порог покрытия: 98%)
[Novel:11, Ch:4] ✅ JSON успешно распарсен
[Novel:11, Ch:4] Проверка объема: RU 100.97%, ZH 99.29%
[Novel:11, Ch:4] ✅ Выравнивание успешно: 32 пар, качество 0.97

# Fallback лог:
[Novel:11, Ch:1] Попытка 3/3 (порог покрытия: 95%)
[Novel:11, Ch:1] Проверка объема: RU 99.91%, ZH 93.15%
[Novel:11, Ch:1] ⚠️ Потеря текста! ZH: 93.15% (нужно ≥95%)
[Novel:11, Ch:1] ❌ Используем fallback regex-выравнивание
```
