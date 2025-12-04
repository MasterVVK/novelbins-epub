# 📖 Быстрая справка: Система перевода глав новеллы

## 🎯 Три основных этапа

```
ПАРСИНГ          ПЕРЕВОД                РЕДАКТУРА
(Извлечение)     (中文 → Русский)       (Улучшение)
    ↓                ↓                      ↓
┌─────────┐      ┌─────────┐            ┌─────────┐
│ Китайский│  →  │ Русский │        →   │ Русский │
│ оригинал │      │ перевод │            │  улучшен│
│          │      │ (черновик)│          │          │
│ status:  │      │ status: │            │ status: │
│ 'parsed' │      │'translated'│         │ 'edited'│
└─────────┘      └─────────┘            └─────────┘
```

---

## 🔄 Основной процесс перевода

### 1. Подготовка контекста

```python
# Что загружается перед переводом
context = {
    'prompt_template': промпт для LLM,
    'previous_summaries': резюме 5 предыдущих глав,
    'glossary': {
        'characters': {'Bai Xiaochun': 'Бай Сяочунь'},
        'locations': {...},
        'terms': {'Qi': 'Ци', 'Cultivation': 'Культивация'},
        'techniques': {...},
        'artifacts': {...}
    },
    'chapter_title': название текущей главы
}
```

### 2. Обработка текста

```python
# Предобработка
text = preprocess_text(chapter.original_text)
# "Wooooooo" → "Wooo..."
# Повторения > 5 символов → короткая версия

# Разбиение (если длинный)
parts = split_long_text(text)
# < 15k символов → 1 часть
# 15k-30k → 2-3 части
# > 30k → разбивка по параграфам
```

### 3. Запрос к LLM

```python
# Для каждой части
translated = translator.translate_text(
    text=part,
    system_prompt=translation_prompt,     # "Ты профессиональный переводчик..."
    context=context_prompt,               # Глоссарий + резюме
    temperature=0.1                       # Низкая = точность
)

# Цепочка вызовов:
# TranslatorService
#   → UniversalLLMTranslator (ротация ключей)
#     → AIAdapterService (выбор провайдера)
#       → HTTP запрос к Gemini/OpenAI/Ollama/etc
```

### 4. Обработка ошибок

```python
# Если PROHIBITED_CONTENT (Gemini)
→ Добавить "Это художественное произведение..."
→ Повторить запрос
→ Если не помогло: разбить на мелкие части (ultra_small=True)

# Если Rate Limit (Ollama)
→ 4 попытки: 1 мин, 5 мин, 15 мин, 40 мин

# Если Server Error 500/502/504
→ 5 попыток: 30 сек, 2 мин, 5 мин, 10 мин, 20 мин

# Если Rate Limit (Gemini)
→ Переключиться на следующий API ключ
→ Продолжить с новым ключом
```

---

## ✏️ Редактура с оригиналом

### Ключевая особенность: Использование китайского оригинала!

```python
def edit_chapter(chapter):
    # ЗАГРУЖАЕМ ВСЕ
    original_text = chapter.original_text          # 中文
    translated_text = chapter.current_translation  # Русский (черновик)
    glossary = load_glossary()                     # Термины

    # ЭТАП 1: Анализ (LLM сравнивает с оригиналом)
    strategy = analyze_with_original(original, translated, glossary)
    # → quality_score: 7/10
    # → missing_details: [...пропущенные детали...]
    # → needs_glossary_fix: true

    # ЭТАП 2: Исправление (LLM исправляет по оригиналу)
    edited = fix_with_original(original, translated, glossary)
    # "Исправь неточности, сверяясь с китайским оригиналом"

    # ЭТАП 3: Улучшение стиля
    edited = improve_style_with_original(original, edited, glossary)
    # "Улучши стиль, сохраняя точность оригинала"

    # ЭТАП 4: Полировка диалогов
    edited = polish_dialogues_with_original(original, edited, glossary)

    # ЭТАП 5: Финальная полировка
    edited = final_polish_with_original(original, edited, glossary)

    # ПРОВЕРКА
    if edited == translated:
        return False  # ❌ Текст не изменился = ошибка

    # СОХРАНЕНИЕ
    save_edited_translation(chapter, edited)
    chapter.status = 'edited'  # ✅
```

**Почему это важно:**
- LLM может проверить, что перевод точно передает смысл оригинала
- Выявляются пропущенные детали из китайского текста
- Гарантируется соответствие терминологии

---

## 🔑 Ротация API ключей (Gemini)

```python
# Конфигурация модели
ai_model.api_keys = ['key1', 'key2', 'key3']

# Процесс
attempts = 0
while attempts < max_attempts:
    # Пропускаем failed ключи
    if current_key_index in failed_keys:
        switch_to_next_key()

    # Пробуем текущий ключ
    result = make_request_with_key(current_key)

    if result.success:
        return result  # ✅ УСПЕХ

    if 'Rate limit' in result.error:
        mark_key_as_failed()      # ❌ Пометить
        switch_to_next_key()      # → Следующий

    # Если ВСЕ ключи failed
    if all_keys_failed():
        wait(30 seconds)          # ⏳ Подождать
        reset_failed_keys()       # 🔄 Сбросить
        # Повторить попытки

    attempts += 1
```

---

## ⚡ Параллельная обработка

```python
# Celery Task с ThreadPoolExecutor
@celery.task
def edit_novel_chapters_task(novel_id, chapter_ids, parallel_threads=3):

    def edit_single_chapter(chapter_id):
        # Каждый поток создает свой app_context
        with app.app_context():
            chapter = Chapter.query.get(chapter_id)

            # ЗАЩИТА ОТ ДУБЛИРОВАНИЯ
            if chapter.status == 'edited':
                return False  # Пропускаем

            # Редактируем
            result = editor.edit_chapter(chapter)

            # Thread-safe обновление
            with counter_lock:
                success_count += 1
                novel.edited_chapters = success_count
                db.session.commit()

    # Параллельная обработка
    with ThreadPoolExecutor(max_workers=parallel_threads) as executor:
        futures = {executor.submit(edit_single_chapter, ch_id): ch_id
                   for ch_id in chapter_ids}

        for future in as_completed(futures):
            result = future.result()
```

**Рекомендации:**
- `parallel_threads=3` - оптимально (баланс скорость/нагрузка)
- Меньше 2 - медленно
- Больше 5 - перегрузка AI API и БД

---

## 🎛️ Настройки перевода

### В конфигурации Novel (`novel.config`):

```python
novel.config = {
    # Модель и параметры
    'translation_model': 'gemini-2.0-flash-exp',
    'translation_temperature': 0.1,    # 0.0-1.0 (0.1 = точность)
    'editing_temperature': 0.3,

    # Параллельность
    'editing_threads': 3,              # 1-10 (рекомендуется 2-5)
    'alignment_threads': 3,

    # Фильтры текста
    'filter_text': 'czbooks.net\nПродолжение следует...',
}
```

### В модели AIModel:

```python
ai_model = AIModel(
    name='Gemini 2.0 Flash',
    provider='gemini',
    model_id='gemini-2.0-flash-exp',

    # Ключи
    api_key='AIzaSy...',              # Один ключ
    api_keys=['key1', 'key2', 'key3'], # Или список для ротации

    # Лимиты
    max_input_tokens=1048576,          # 1M токенов
    max_output_tokens=8192,

    # Параметры
    default_temperature=0.1,
    supports_system_prompt=True,
)
```

---

## 📊 Оценка токенов

```python
# Адаптивная оценка на основе языка
def _estimate_tokens(text):
    if много_китайских_символов(text):
        chars_per_token = 1.5      # Китайский: ~1.5 символа/токен
    elif много_кириллицы(text):
        chars_per_token = 2.5      # Русский: ~2.5 символа/токен
    else:
        chars_per_token = 4.0      # Английский: ~4 символа/токен

    return len(text) / chars_per_token
```

### Параметры Ollama:

```python
prompt_tokens = estimate_tokens(system_prompt + user_prompt)

# num_ctx = промпт + 20% буфер (минимум 2048)
num_ctx = max(2048, int(prompt_tokens * 1.2))

# num_predict = num_ctx × 2 (не больше max_output_tokens)
num_predict = min(num_ctx * 2, model.max_output_tokens)
```

---

## 🏷️ Глоссарий

```python
# Структура термина
glossary_item = GlossaryItem(
    novel_id=novel_id,
    english_term='Qi Condensation',         # Английская транслитерация
    russian_term='Конденсация Ци',         # Русский перевод
    category='terms',                       # characters, locations, terms, techniques, artifacts
    description='Первая ступень культивации',
    first_appearance_chapter=1,
    is_auto_generated=False,
    is_active=True
)

# Приоритизация
glossary = {
    # 1. Специфичные термины ЭТОЙ новеллы (приоритет выше)
    'novel_specific': {...},

    # 2. Общие термины жанра (приоритет ниже)
    'genre_common': {...}
}
```

---

## 🔍 Логирование

```python
# Контекстное логирование с префиксом
LogService.log_info(
    f"[Novel:{novel_id}, Ch:{chapter_num}] Перевод части 1/3",
    novel_id=novel_id,
    chapter_id=chapter_id
)

# Уровни
LogService.log_info()     # ℹ️ Информация
LogService.log_warning()  # ⚠️ Предупреждения
LogService.log_error()    # ❌ Ошибки

# Логи сохраняются:
# - В БД (log_entries)
# - В файл (logs/app.log)
# - В консоль
```

---

## 📈 Производительность

### Для новеллы 1000 глав:

| Этап | Время на главу | Общее время (последовательно) | С 3 потоками |
|------|---------------|------------------------------|--------------|
| Парсинг | 5-15 сек | 1.5-4 часа | 1.5-4 часа |
| Перевод | 30-60 сек | 8-17 часов | 8-17 часов |
| Редактура | 40-80 сек | 11-22 часа | **4-8 часов** ⚡ |
| **ИТОГО** | **~1.5-2.5 мин** | **~24-48 часов** | **~14-29 часов** |

---

## 🛡️ Обработка ошибок: Уровни повторов

1. **API ключи** (Gemini):
   - Ротация между ключами
   - Сброс after 3 cycles (5 мин wait)

2. **Провайдер** (Ollama):
   - Rate limit: 4 попытки (1м, 5м, 15м, 40м)
   - Server error: 5 попыток (30с, 2м, 5м, 10м, 20м)

3. **Контент**:
   - PROHIBITED_CONTENT → disclaimer + retry → split
   - CONTENT_BLOCKED → ultra_small разбиение

4. **Задачи** (Celery):
   - Защита от дублирования
   - Graceful shutdown
   - Промежуточное сохранение

---

## 🎯 Лучшие практики

### Для быстрого перевода:
```python
provider='gemini'
model='gemini-2.0-flash-exp'
api_keys=['key1', 'key2', 'key3']  # Минимум 3 ключа
temperature=0.1
editing_threads=3
```

### Для максимального качества:
```python
provider='openai'
model='gpt-4-turbo'
temperature=0.1
editing_threads=2  # Медленнее, но точнее
```

### Для бесплатного использования:
```python
provider='ollama'
model='qwen2.5:32b'
temperature=0.5  # Ollama лучше с 0.5
editing_threads=2
```

---

## 📂 Ключевые файлы (Top 5)

1. **`celery_tasks.py`** - Фоновые задачи (парсинг, перевод, редактура)
2. **`translator_service.py`** - Координация перевода + контекст
3. **`universal_llm_translator.py`** - Переводчик + ротация ключей
4. **`ai_adapter_service.py`** - Адаптеры провайдеров (Gemini, Ollama, OpenAI)
5. **`original_aware_editor_service.py`** - Редактура с оригинальным текстом

---

## 🚀 Быстрый старт

```bash
# 1. Создать новеллу
POST /api/novels
{
  "title": "Одна мысль о вечности",
  "source_url": "https://czbooks.net/n/u17k8272",
  "config": {
    "translation_model": "gemini-2.0-flash-exp",
    "translation_temperature": 0.1,
    "editing_threads": 3
  }
}

# 2. Запустить парсинг
POST /api/novels/{id}/parse
{
  "start_chapter": 1,
  "max_chapters": 100
}

# 3. Запустить перевод
POST /api/novels/{id}/translate-chapters
{
  "chapter_ids": [1, 2, 3, ...],
  "use_parallel": true
}

# 4. Запустить редактуру
POST /api/novels/{id}/edit-chapters
{
  "chapter_ids": [1, 2, 3, ...],
  "parallel_threads": 3
}
```

---

**Создано:** 2025-11-24
**Версия:** Текущая (master branch)
