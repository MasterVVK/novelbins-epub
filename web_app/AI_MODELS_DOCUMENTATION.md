# Система управления AI моделями

## Обзор

Система управления AI моделями позволяет настраивать и использовать различные LLM для перевода и редактирования текстов. Поддерживаются следующие провайдеры:

- **Google Gemini** (gemini-2.5-flash, gemini-2.5-pro)
- **OpenAI** (GPT-4o, GPT-4o-mini, GPT-3.5-turbo)
- **Anthropic** (Claude 3.5 Sonnet, Claude 3 Opus)
- **Ollama** (локальные модели: qwen2.5, llama3, mistral и др.)

## Доступ к системе

Система управления моделями доступна по адресу:
```
http://192.168.0.58:5001/ai-models
```

Или через боковое меню: **AI Модели**

## Основные функции

### 1. Просмотр моделей
- Модели сгруппированы по провайдерам
- Отображаются характеристики: скорость, качество, стоимость
- Показан статус подключения и последнее тестирование

### 2. Добавление новой модели

1. Нажмите кнопку **"Добавить модель"**
2. Выберите провайдера из списка
3. Заполните обязательные поля:
   - Название модели
   - ID модели (например: `gemini-2.5-flash`)
   - API ключ (кроме Ollama)
   - API Endpoint

4. Настройте параметры:
   - Максимальные токены входа/выхода
   - Температура по умолчанию
   - Рейтинги характеристик

5. Нажмите **"Создать модель"**

### 3. Тестирование модели

Для проверки работоспособности:
1. Нажмите кнопку тестирования (▶️) рядом с моделью
2. Система отправит тестовый запрос
3. Результат отобразится во всплывающем окне

### 4. Редактирование модели

1. Нажмите кнопку редактирования (✏️)
2. Измените необходимые параметры
3. Нажмите **"Сохранить изменения"**

### 5. Установка модели по умолчанию

1. Нажмите звёздочку (⭐) рядом с моделью
2. Эта модель будет использоваться для всех новых переводов

## Настройка провайдеров

### Google Gemini
```yaml
Провайдер: gemini
API Endpoint: https://generativelanguage.googleapis.com/v1beta
Требуется API ключ: Да
Модели:
  - gemini-2.5-flash (быстрая, экономичная)
  - gemini-2.5-pro (качественная, дорогая)
```

### OpenAI
```yaml
Провайдер: openai
API Endpoint: https://api.openai.com/v1
Требуется API ключ: Да
Модели:
  - gpt-4o (последняя, качественная)
  - gpt-4o-mini (быстрая, дешёвая)
  - gpt-3.5-turbo (классическая)
```

### Anthropic
```yaml
Провайдер: anthropic
API Endpoint: https://api.anthropic.com/v1
Требуется API ключ: Да
Модели:
  - claude-3-5-sonnet-20241022
  - claude-3-opus-20240229
```

### Ollama (локальные модели)
```yaml
Провайдер: ollama
API Endpoint: http://localhost:11434/api
Требуется API ключ: Нет
Модели: автоматически загружаются из Ollama
```

## Структура данных

### Таблица ai_models

```sql
CREATE TABLE ai_models (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    model_id VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    api_endpoint VARCHAR(500),
    api_key TEXT,
    max_input_tokens INTEGER,
    max_output_tokens INTEGER,
    default_temperature FLOAT,
    speed_rating INTEGER,
    quality_rating INTEGER,
    cost_rating INTEGER,
    is_active BOOLEAN,
    is_default BOOLEAN,
    created_at DATETIME,
    updated_at DATETIME,
    last_tested_at DATETIME,
    test_status VARCHAR(50)
);
```

## API Endpoints

### Создание модели
```http
POST /api/ai-models
Content-Type: application/json

{
    "name": "Gemini 2.5 Flash",
    "model_id": "gemini-2.5-flash",
    "provider": "gemini",
    "api_key": "YOUR_API_KEY",
    "max_input_tokens": 1000000,
    "max_output_tokens": 256000
}
```

### Обновление модели
```http
PUT /api/ai-models/{model_id}
Content-Type: application/json

{
    "name": "Updated Name",
    "api_key": "NEW_API_KEY",
    "is_active": true
}
```

### Удаление модели
```http
DELETE /api/ai-models/{model_id}
```

### Тестирование модели
```http
POST /api/ai-models/{model_id}/test
```

### Установка модели по умолчанию
```http
POST /api/ai-models/{model_id}/set-default
```

### Получение моделей Ollama
```http
POST /api/ollama/models
Content-Type: application/json

{
    "endpoint": "http://localhost:11434/api"
}
```

## Интеграция с системой перевода

### Использование в TranslatorService

```python
from app.services.ai_adapter_service import AIAdapterService

# Использование модели по умолчанию
adapter = AIAdapterService()

# Использование конкретной модели
adapter = AIAdapterService(model_id=1)

# Генерация контента
result = await adapter.generate_content(
    system_prompt="Ты профессиональный переводчик",
    user_prompt="Переведи: Hello, world!",
    temperature=0.3,
    max_tokens=1000
)

if result['success']:
    print(result['content'])
else:
    print(f"Ошибка: {result['error']}")
```

## Рекомендации по выбору модели

### Для черновых переводов
- **Gemini 2.5 Flash** - быстрая, дешёвая, подходит для массового перевода
- **GPT-4o-mini** - альтернатива от OpenAI
- **Qwen 2.5 (Ollama)** - бесплатная локальная модель

### Для финальных переводов
- **Gemini 2.5 Pro** - баланс качества и скорости
- **GPT-4o** - высокое качество, хорошее понимание контекста
- **Claude 3.5 Sonnet** - отличная работа с длинным контекстом

### Для редактирования
- **Claude 3.5 Sonnet** - лучший выбор для литературной обработки
- **GPT-4o** - хорошая альтернатива
- **Gemini 2.5 Pro** - экономичный вариант

## Устранение неполадок

### Модель не тестируется
1. Проверьте правильность API ключа
2. Убедитесь, что API endpoint доступен
3. Для Ollama проверьте, что сервер запущен: `ollama serve`

### Ошибка "Rate limit"
1. Добавьте несколько API ключей для ротации
2. Уменьшите частоту запросов
3. Используйте другую модель

### Ollama не показывает модели
1. Убедитесь, что Ollama запущен: `systemctl status ollama`
2. Проверьте список моделей: `ollama list`
3. Скачайте модель: `ollama pull qwen2.5:32b`

## Миграция с старой системы

Если у вас уже есть API ключи в настройках:

```python
# Автоматический импорт ключей Gemini
python -c "
from app import create_app
from app.services.settings_service import SettingsService
from app.models.ai_model import AIModel
from app import db

app = create_app()
with app.app_context():
    keys = SettingsService.get_gemini_api_keys()
    if keys:
        model = AIModel.query.filter_by(model_id='gemini-2.5-flash').first()
        if model:
            model.api_key = keys[0]
            db.session.commit()
            print(f'API ключ добавлен к модели {model.name}')
"
```

## Дальнейшее развитие

Планируемые улучшения:
1. Автоматическая ротация API ключей
2. Статистика использования каждой модели
3. Расчёт стоимости использования
4. A/B тестирование моделей
5. Кеширование результатов
6. Поддержка streaming ответов