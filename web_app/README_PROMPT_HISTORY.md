# Управление историей промптов

## 📊 **Текущее состояние**

**Да, промпты сохраняются всегда** при выполнении запросов к LLM API для **перевода и редактуры**, но с улучшенной логикой:

### ✅ **Когда сохраняются промпты:**

1. **При успешном запросе:**
   - Системный и пользовательский промпт
   - Ответ API
   - Метаданные (ключ, модель, токены, время выполнения)
   - Статус: `success = True`

2. **При неудачном запросе:**
   - Системный и пользовательский промпт
   - Сообщение об ошибке
   - Метаданные запроса
   - Статус: `success = False`

### 📝 **Типы промптов:**

1. **Перевод:**
   - `translation` - основной перевод текста
   - `summary` - генерация резюме главы
   - `terms_extraction` - извлечение новых терминов

2. **Редактура:**
   - `editing_analysis` - анализ качества текста
   - `editing_style` - улучшение стиля
   - `editing_dialogue` - полировка диалогов
   - `editing_final` - финальная полировка

### ⚙️ **Управление сохранением:**

#### **Включение/выключение:**
```python
# При создании TranslatorService
config = {
    'save_prompt_history': False  # Отключить сохранение
}
translator_service = TranslatorService(config)

# Или динамически
translator_service.translator.set_save_prompt_history(False)
```

#### **Проверка статуса:**
```python
status = translator_service.translator.get_prompt_history_status()
print(f"Сохранение промптов: {'включено' if status else 'отключено'}")
```

## 🔍 **Просмотр истории промптов**

### **Получение истории для главы:**
```python
from app.models import PromptHistory

# Вся история главы
history = PromptHistory.get_chapter_history(chapter_id=123)

# Только переводы
translations = PromptHistory.get_chapter_history(
    chapter_id=123, 
    prompt_type='translation'
)

# Только резюме
summaries = PromptHistory.get_chapter_history(
    chapter_id=123, 
    prompt_type='summary'
)

# Только извлечение терминов
terms = PromptHistory.get_chapter_history(
    chapter_id=123, 
    prompt_type='terms_extraction'
)

# Только редактура
editing = PromptHistory.get_chapter_history(
    chapter_id=123, 
    prompt_type='editing_analysis'
)

# Все этапы редактуры
all_editing = PromptHistory.query.filter(
    PromptHistory.chapter_id == 123,
    PromptHistory.prompt_type.like('editing_%')
).order_by(PromptHistory.created_at).all()
```

### **Анализ ошибок:**
```python
# Все неудачные промпты
failed_prompts = PromptHistory.query.filter_by(success=False).all()

# Ошибки для конкретной главы
chapter_errors = PromptHistory.query.filter_by(
    chapter_id=123, 
    success=False
).all()

# Ошибки по типу
translation_errors = PromptHistory.query.filter_by(
    prompt_type='translation',
    success=False
).all()

# Ошибки редактуры
editing_errors = PromptHistory.query.filter(
    PromptHistory.prompt_type.like('editing_%'),
    PromptHistory.success == False
).all()
```

### **Статистика:**
```python
from sqlalchemy import func

# Общая статистика
stats = db.session.query(
    PromptHistory.prompt_type,
    func.count(PromptHistory.id).label('total'),
    func.sum(func.case([(PromptHistory.success, 1)], else_=0)).label('success'),
    func.avg(PromptHistory.execution_time).label('avg_time')
).group_by(PromptHistory.prompt_type).all()

for stat in stats:
    print(f"{stat.prompt_type}: {stat.total} запросов, "
          f"{stat.success} успешных, "
          f"среднее время: {stat.avg_time:.2f}с")
```

## 📋 **Структура таблицы prompt_history**

```sql
CREATE TABLE prompt_history (
    id INTEGER PRIMARY KEY,
    chapter_id INTEGER NOT NULL,
    prompt_type VARCHAR(50) NOT NULL,  -- translation, summary, terms_extraction
    system_prompt TEXT NOT NULL,
    user_prompt TEXT NOT NULL,
    response TEXT,
    api_key_index INTEGER,
    model_used VARCHAR(100),
    temperature FLOAT,
    tokens_used INTEGER,
    finish_reason VARCHAR(50),
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    execution_time FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id)
);
```

## 🚀 **Примеры использования**

### **Отладка проблем с переводом:**
```python
# Найти все ошибки для главы
errors = PromptHistory.query.filter_by(
    chapter_id=123,
    success=False
).order_by(PromptHistory.created_at.desc()).all()

for error in errors:
    print(f"Ошибка {error.prompt_type}: {error.error_message}")
    print(f"Промпт: {error.system_prompt[:200]}...")
    print(f"Время: {error.created_at}")
    print("---")
```

### **Анализ процесса редактуры:**
```python
# Проследить весь процесс редактуры главы
editing_steps = PromptHistory.query.filter(
    PromptHistory.chapter_id == 123,
    PromptHistory.prompt_type.like('editing_%')
).order_by(PromptHistory.created_at).all()

print("Процесс редактуры главы 123:")
for step in editing_steps:
    print(f"Этап: {step.prompt_type}")
    print(f"Время выполнения: {step.execution_time:.2f}с")
    print(f"Успех: {'✅' if step.success else '❌'}")
    if step.success:
        print(f"Результат: {step.response[:100]}...")
    else:
        print(f"Ошибка: {step.error_message}")
    print("---")
```

### **Анализ производительности:**
```python
# Самые медленные запросы
slow_queries = PromptHistory.query.filter(
    PromptHistory.execution_time > 60  # больше минуты
).order_by(PromptHistory.execution_time.desc()).limit(10).all()

for query in slow_queries:
    print(f"Глава {query.chapter_id}, тип: {query.prompt_type}, "
          f"время: {query.execution_time:.2f}с")
```

### **Отключение для тестирования:**
```python
# Создать сервис без сохранения истории
test_config = {
    'save_prompt_history': False,
    'api_keys': ['test_key'],
    'model_name': 'gemini-pro'
}

test_translator = TranslatorService(test_config)
# Теперь промпты не будут сохраняться
```

## ⚠️ **Важные моменты**

1. **Производительность:** Сохранение промптов может замедлить процесс при большом объеме
2. **Место на диске:** Промпты могут занимать много места в базе данных
3. **Безопасность:** Промпты содержат исходный текст, убедитесь в безопасности БД
4. **Очистка:** Регулярно очищайте старые записи для экономии места

### **Рекомендации:**

- **Для продакшена:** Включить сохранение для отладки
- **Для тестирования:** Отключить для ускорения
- **Для больших проектов:** Настроить автоматическую очистку старых записей
- **Для безопасности:** Шифровать чувствительные данные в промптах 