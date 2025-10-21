# Обработка лимитов Ollama API

## Типы ошибок

Ollama API (особенно облачные модели) имеют различные типы ошибок:

### 1. **Hourly Limit** (Часовой лимит) ⚠️
**Ошибка**: `you've reached your hourly usage limit`

**Поведение системы**:
- ✅ Автоматические повторные попытки с прогрессивными интервалами
- 4 попытки с ожиданием: 1 мин → 5 мин → 15 мин → 40 мин
- Общее время ожидания: ~61 минута

**Логирование**:
```
⚠️ Достигнут часовой лимит использования модели kimi-k2:1t-cloud
⏳ Попытка 1/4: Ожидание 1 минуту перед повторным запросом...
```

### 2. **Daily Limit** (Дневной лимит) 🚫
**Ошибка**: `you've reached your daily usage limit`

**Поведение системы**:
- ❌ Повторные попытки НЕ выполняются (бессмысленно)
- Немедленная остановка перевода
- Сохранение ошибки в `prompt_history`

**Логирование**:
```
🚫 Достигнут дневной лимит использования модели kimi-k2:1t-cloud
🛑 Повторные попытки невозможны - лимит действует дневной день
💡 Рекомендации:
   1. Используйте другую модель Ollama
   2. Дождитесь сброса лимита
   3. Обновите тарифный план
```

### 3. **Weekly Limit** (Недельный лимит) 🚫
**Ошибка**: `you've reached your weekly usage limit`

**Поведение системы**:
- ❌ Повторные попытки НЕ выполняются (бессмысленно)
- Немедленная остановка перевода
- Сохранение ошибки в `prompt_history`

**Логирование**:
```
🚫 Достигнут недельный лимит использования модели kimi-k2:1t-cloud
🛑 Повторные попытки невозможны - лимит действует недельную неделю
💡 Рекомендации:
   1. Используйте другую модель Ollama
   2. Дождитесь сброса лимита
   3. Обновите тарифный план
```

### 4. **Upstream Error** (Ошибка upstream) ⚠️
**Ошибка**: `upstream error` (HTTP 502)

**Поведение системы**:
- ✅ Автоматические повторные попытки с короткими интервалами
- 2 попытки с ожиданием: 30 сек → 5 мин
- Общее время ожидания: ~5.5 минут

**Логирование**:
```
⚠️ Временная upstream error (502) для модели kimi-k2:1t-cloud
⏳ Попытка 1/2: Ожидание 30 секунд перед повторным запросом...
🔄 Повторная попытка 1/2 запроса к kimi-k2:1t-cloud
```

### 4.1. **Upstream Timeout** (Таймаут upstream) ⚠️
**Ошибка**: `upstream timeout` (HTTP 504)

**Причины**:
- Сервер Ollama не успел обработать запрос
- Модель слишком долго генерирует ответ
- Перегрузка сервера

**Поведение системы**:
- ✅ Автоматические повторные попытки с короткими интервалами
- 2 попытки с ожиданием: 30 сек → 5 мин
- Общее время ожидания: ~5.5 минут

**Логирование**:
```
⚠️ Временная upstream timeout (504) для модели kimi-k2:1t-cloud
   Текст ошибки: Ошибка Ollama: upstream timeout
⏳ Попытка 1/2: Ожидание 30 секунд перед повторным запросом...
🔄 Повторная попытка 1/2 запроса к kimi-k2:1t-cloud
```

### 5. **Server Error** (Внутренняя ошибка сервера) ⚠️
**Ошибка**: `unmarshal: unexpected end of JSON input` (HTTP 500)

**Причины**:
- Прерванный ответ от сервера
- Невалидный JSON в ответе
- Внутренняя ошибка Ollama

**Поведение системы**:
- ✅ Автоматические повторные попытки с короткими интервалами
- 2 попытки с ожиданием: 30 сек → 5 мин
- Общее время ожидания: ~5.5 минут

**Логирование**:
```
⚠️ Временная внутренняя ошибка сервера (500) для модели kimi-k2:1t-cloud
   Текст ошибки: Ошибка Ollama: unmarshal: unexpected end of JSON input
⏳ Попытка 1/2: Ожидание 30 секунд перед повторным запросом...
🔄 Повторная попытка 1/2 запроса к kimi-k2:1t-cloud
```

## HTTP коды ошибок

| HTTP Код | Тип ошибки | Пример сообщения | Повторы |
|----------|-----------|------------------|---------|
| 402      | Weekly/Daily | `you've reached your weekly usage limit` | ❌ Нет |
| 429      | Hourly (обычно) | `you've reached your hourly usage limit` | ✅ 4 попытки |
| 500      | Server Error | `unmarshal: unexpected end of JSON input` | ✅ 2 попытки |
| 502      | Upstream Error | `upstream error` | ✅ 2 попытки |
| 504      | Upstream Timeout | `upstream timeout` | ✅ 2 попытки |

## Реализация

### Файлы

1. **`web_app/app/services/ai_adapter_service.py`** (строки 380-395)
   - Определение типа ошибки из ответа Ollama
   - Классификация: `weekly_limit`, `daily_limit`, `rate_limit`

2. **`web_app/app/services/universal_llm_translator.py`** (строки 213-227)
   - Обработка недельных/дневных лимитов БЕЗ повторов
   - Обработка часовых лимитов С прогрессивными повторами

### Логика определения типа ошибки

```python
if 'weekly usage limit' in error_detail_lower:
    error_type = 'weekly_limit'
elif 'daily usage limit' in error_detail_lower:
    error_type = 'daily_limit'
elif 'hourly usage limit' in error_detail_lower or 'usage limit' in error_detail_lower:
    error_type = 'rate_limit'
elif 'upstream timeout' in error_detail_lower or response.status_code == 504:
    error_type = 'upstream_timeout'
elif 'upstream error' in error_detail_lower or response.status_code == 502:
    error_type = 'upstream_error'
elif 'unmarshal' in error_detail_lower or 'unexpected end of json' in error_detail_lower or response.status_code == 500:
    error_type = 'server_error'
```

### Обработка в цикле перевода

```python
# Недельный/дневной лимит - немедленная остановка
if error_type in ['weekly_limit', 'daily_limit']:
    log_error("Повторы невозможны")
    save_to_history(success=False)
    return None

# Server/Upstream error/timeout - короткие повторы (30 сек, 5 мин)
if error_type in ['server_error', 'upstream_error', 'upstream_timeout']:
    retry_delays = [(30, "30 секунд"), (300, "5 минут")]
    for attempt, delay in retry_delays:
        wait(delay)
        retry = make_request()
        if success:
            return result

# Часовой лимит - прогрессивные повторы (1 мин, 5 мин, 15 мин, 40 мин)
if error_type == 'rate_limit':
    retry_delays = [(60, "1 минуту"), (300, "5 минут"), (900, "15 минут"), (2400, "40 минут")]
    for attempt, delay in retry_delays:
        wait(delay)
        retry = make_request()
        if success:
            return result
```

## Мониторинг лимитов

### Запрос к базе данных

Просмотр всех ошибок лимитов за последние 7 дней:

```sql
SELECT
    id,
    chapter_id,
    prompt_type,
    error_message,
    created_at
FROM prompt_history
WHERE success = 0
  AND (
    error_message LIKE '%weekly usage limit%'
    OR error_message LIKE '%daily usage limit%'
    OR error_message LIKE '%hourly usage limit%'
  )
  AND created_at > datetime('now', '-7 days')
ORDER BY created_at DESC;
```

### Статистика по типам лимитов

```sql
SELECT
    CASE
        WHEN error_message LIKE '%weekly%' THEN 'Weekly Limit'
        WHEN error_message LIKE '%daily%' THEN 'Daily Limit'
        WHEN error_message LIKE '%hourly%' THEN 'Hourly Limit'
        ELSE 'Other'
    END as limit_type,
    COUNT(*) as count,
    MIN(created_at) as first_occurrence,
    MAX(created_at) as last_occurrence
FROM prompt_history
WHERE success = 0
  AND error_message LIKE '%usage limit%'
  AND created_at > datetime('now', '-7 days')
GROUP BY limit_type
ORDER BY count DESC;
```

## Рекомендации при достижении лимитов

### При часовом лимите (Hourly)
✅ **Система справится автоматически**
- Подождите до 61 минуты
- Система автоматически повторит запросы
- Перевод продолжится после снятия лимита

### При дневном лимите (Daily)
⚠️ **Требуется действие пользователя**
1. Дождитесь следующего дня (сброс обычно в 00:00 UTC)
2. Используйте альтернативную модель Ollama (если есть)
3. Переключитесь на другой провайдер (Gemini, OpenAI, Anthropic)
4. Обновите тарифный план Ollama

### При недельном лимите (Weekly)
🚫 **Требуется действие пользователя**
1. Дождитесь следующей недели (сброс обычно понедельник 00:00 UTC)
2. Используйте альтернативную модель Ollama (если есть)
3. Переключитесь на другой провайдер (Gemini, OpenAI, Anthropic)
4. Обновите тарифный план Ollama

### При ошибке upstream/server (Upstream Error / Server Error / Upstream Timeout)
✅ **Система справится автоматически**
- Подождите до 5.5 минут
- Система автоматически повторит запросы (2 попытки)
- Перевод продолжится после восстановления сервера
- Если проблема сохраняется после 2 попыток - попробуйте позже

**Типичные причины**:
- Временная перегрузка сервера Ollama
- Прерванное сетевое соединение
- Проблемы с облачной инфраструктурой
- Модель слишком долго генерирует ответ (504 timeout)

## Пример реального лога

### Недельный лимит (текущая версия)

```
06:49:59 ERROR [system] Ошибка ollama: Ошибка Ollama: you've reached your weekly usage limit, please upgrade to continue (тип: weekly_limit)
06:49:59 ERROR [system] Полный результат ошибки: {'success': False, 'error': "Ошибка Ollama: you've reached your weekly usage limit, please upgrade to continue", 'error_type': 'weekly_limit', 'status_code': 402}
06:49:59 ERROR [system] 🚫 Достигнут недельный лимит использования модели kimi-k2:1t-cloud
06:49:59 ERROR [system]    Текст ошибки: Ошибка Ollama: you've reached your weekly usage limit, please upgrade to continue
06:49:59 ERROR [system] 🛑 Повторные попытки невозможны - лимит действует недельную неделю
06:49:59 ERROR [system] 💡 Рекомендации:
06:49:59 ERROR [system]    1. Используйте другую модель Ollama
06:49:59 ERROR [system]    2. Дождитесь сброса лимита
06:49:59 ERROR [system]    3. Обновите тарифный план
06:49:59 INFO [system] Промпт сохранен в историю (тип: translation, успех: False)
06:49:59 ERROR [translator] Ошибка перевода части 1 главы 90
```

### Часовой лимит с успешным восстановлением

```
21:33:36 ERROR [system] Ошибка ollama: Ошибка Ollama: you've reached your hourly usage limit (тип: rate_limit)
21:33:36 WARNING [system] ⚠️ Достигнут часовой лимит использования модели kimi-k2:1t-cloud
21:33:36 WARNING [system] ⏳ Попытка 1/4: Ожидание 1 минуту перед повторным запросом...
21:34:36 INFO [system] 🔄 Повторная попытка 1/4 запроса к kimi-k2:1t-cloud
21:34:40 INFO [system] ✅ Повторная попытка 1 успешна!
21:34:40 INFO [system] Промпт сохранен в историю (тип: translation, успех: True)
```

---

**Дата создания**: 18 октября 2025
**Версия**: 1.3 (добавлена обработка upstream timeout 504)
**Статус**: ✅ Реализовано и протестировано
