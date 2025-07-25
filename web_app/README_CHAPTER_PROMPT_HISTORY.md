# Просмотр истории промптов в главах

## 🎯 **Новая функциональность**

Теперь при просмотре главы можно увидеть **полную историю всех промптов**, которые использовались для перевода и редактуры этой главы.

## 📋 **Что отображается**

### **Основная информация:**
- **Количество запросов** - общее число промптов для главы
- **Группировка по типам** - перевод, редактура, резюме, извлечение терминов
- **Статус выполнения** - успех/ошибка для каждого запроса

### **Детали каждого промпта:**
- **Время выполнения** - когда был отправлен запрос
- **Длительность** - сколько времени занял запрос
- **Использованные токены** - количество токенов (если доступно)
- **Системный промпт** - инструкции для LLM
- **Пользовательский промпт** - текст для обработки + контекст
- **Ответ API** - результат обработки
- **Ошибки** - детали ошибок (если были)
- **Метаданные** - модель, ключ API, температура

## 🚀 **Как использовать**

### **1. Просмотр истории промптов:**
1. Откройте главу в веб-интерфейсе
2. Прокрутите вниз до секции "История промптов"
3. Разверните нужные группы промптов

### **2. Экспорт истории:**
1. Нажмите кнопку "Экспорт промптов"
2. Скачается JSON файл с полной историей
3. Файл содержит все промпты и метаданные

### **3. Копирование промптов:**
1. Нажмите кнопку 📋 рядом с промптом
2. Промпт скопируется в буфер обмена
3. Появится уведомление об успешном копировании

## 📊 **Группировка промптов**

### **📝 Перевод:**
- `translation` - основной перевод текста главы
- `summary` - генерация резюме главы  
- `terms_extraction` - извлечение новых терминов

### **✏️ Редактура:**
- `editing_analysis` - анализ качества переведенного текста
- `editing_style` - улучшение стиля текста
- `editing_dialogue` - полировка диалогов
- `editing_final` - финальная полировка

### **🎯 Логика группировки:**
- **Перевод**: все промпты с типами `translation`, `summary`, `terms_extraction`
- **Редактура**: все промпты, начинающиеся с `editing_`
- **Неизвестные типы**: автоматически добавляются в группу "Перевод"
- **Группировка**: по номеру главы (`chapter_number`), а не по ID

## 🔍 **Примеры использования**

### **Отладка проблем с переводом:**
```python
# Получить все ошибки для главы
errors = PromptHistory.query.filter_by(
    chapter_id=123,
    success=False
).all()

for error in errors:
    print(f"Ошибка в {error.prompt_type}: {error.error_message}")
```

### **Анализ производительности:**
```python
# Найти самые медленные запросы
slow_queries = PromptHistory.query.filter(
    PromptHistory.execution_time > 30  # больше 30 секунд
).order_by(PromptHistory.execution_time.desc()).limit(10).all()
```

### **Статистика по главе:**
```python
# Общая статистика главы
stats = db.session.query(
    PromptHistory.prompt_type,
    func.count(PromptHistory.id).label('total'),
    func.avg(PromptHistory.execution_time).label('avg_time'),
    func.sum(func.case([(PromptHistory.success, 1)], else_=0)).label('success_count')
).filter_by(chapter_id=123).group_by(PromptHistory.prompt_type).all()
```

## 📱 **Веб-интерфейс**

### **Структура страницы:**
```
Глава X
├── Исходный текст (англ.)
├── Перевод (рус.)
├── Редактура (рус.)
├── Кнопки действий
└── История промптов
    ├── 📝 Перевод (3) ✅
    │   ├── translation
    │   ├── summary  
    │   └── terms_extraction
    └── ✏️ Редактура (4) ✅
        ├── editing_analysis
        ├── editing_style
        ├── editing_dialogue
        └── editing_final
```

### **Интерактивные элементы:**
- **Аккордеон** - сворачивание/разворачивание групп промптов
- **Цветовая индикация** - зеленый для успеха, красный для ошибок
- **Кнопки копирования** - быстрое копирование промптов
- **Экспорт** - скачивание полной истории в JSON

## 🔧 **API Endpoints**

### **Получение истории промптов:**
```
GET /api/chapters/{chapter_id}/prompt-history
```

**Ответ:**
```json
{
    "chapter_id": 123,
    "chapter_number": 5,
    "total_prompts": 8,
    "prompt_history": [
        {
            "id": 1,
            "prompt_type": "translation",
            "system_prompt": "...",
            "user_prompt": "...",
            "response": "...",
            "success": true,
            "execution_time": 15.2,
            "tokens_used": 2048,
            "model_used": "gemini-pro",
            "created_at": "2024-01-15T10:30:00"
        }
    ]
}
```

## ⚙️ **Настройки**

### **Первоначальная настройка:**
```bash
# Активировать виртуальное окружение
source .venv/bin/activate

# Перейти в папку web_app
cd web_app

# Создать таблицу prompt_history
python migrate_prompt_history.py
```

### **Включение/выключение сохранения:**
```python
# В конфигурации TranslatorService
config = {
    'save_prompt_history': True  # Включить сохранение
}
```

### **Очистка старых записей:**
```python
# Удалить записи старше 30 дней
from datetime import datetime, timedelta
cutoff_date = datetime.utcnow() - timedelta(days=30)
PromptHistory.query.filter(
    PromptHistory.created_at < cutoff_date
).delete()
db.session.commit()
```

### **Тестирование:**
```bash
# Запустить тест истории промптов
python test_prompt_history.py

# Запустить тест группировки промптов
python test_prompt_grouping.py

# Запустить тест поведения при удалении глав
python test_prompt_deletion.py

# Создать тестовые промпты редактуры (для тестирования группировки)
python create_test_editing_prompts.py

# Проверить все типы промптов в базе данных
python check_prompt_types.py

# Исправить типы существующих промптов редактуры
python fix_editing_prompts.py
```

## 🎯 **Преимущества**

1. **Полная прозрачность** - видно все запросы к LLM
2. **Отладка проблем** - легко найти причину ошибок
3. **Оптимизация** - анализ производительности запросов
4. **Обучение** - изучение эффективных промптов
5. **Экспорт** - возможность сохранить историю для анализа
6. **Чистота данных** - промпты удаляются вместе с главами

## 🔧 **Устранение неполадок**

### **Отладочные сообщения:**
В коде добавлены отладочные сообщения, которые показывают:
- Номер главы и её ID
- Количество промптов перевода и редактуры
- Эти сообщения выводятся в консоль при просмотре главы

### **Ошибка "no such table: prompt_history":**
Если при просмотре главы возникает ошибка с отсутствующей таблицей:

1. **Запустите миграцию:**
   ```bash
   cd web_app
   source ../.venv/bin/activate
   python migrate_prompt_history.py
   ```

2. **Проверьте, что таблица создана:**
   ```bash
   python test_prompt_history.py
   ```

3. **Перезапустите веб-приложение** после создания таблицы

### **История промптов не отображается:**
- Убедитесь, что сохранение промптов включено в настройках
- Проверьте, что глава была переведена/отредактирована после включения функции
- Посмотрите логи на наличие ошибок при сохранении промптов

### **Поведение при удалении глав:**
- **Полное удаление**: При удалении главы промпты **УДАЛЯЮТСЯ**
- **Каскадное удаление**: Используется `cascade='all, delete-orphan'`
- **Безвозвратность**: Восстановление главы невозможно - данные теряются
- **Чистота БД**: Это обеспечивает чистоту базы данных
- **Простота**: Нет необходимости в сложной логике восстановления

### **Диагностика проблем с группировкой:**
- **Проблема**: Все промпты отображаются в группе "Перевод"
- **Причина 1**: Отсутствуют промпты редактуры (`editing_*`)
- **Причина 2**: Промпты редактуры сохраняются с типом `translation` вместо `editing_*`
- **Решение 1**: Запустить редактуру главы для создания промптов редактуры
- **Решение 2**: Использовать `fix_editing_prompts.py` для исправления существующих промптов
- **Тестирование**: Использовать `check_prompt_types.py` для диагностики

## 📈 **Статистика**

### **Типичные показатели:**
- **Время перевода:** 10-30 секунд на главу
- **Время редактуры:** 5-15 секунд на этап
- **Использование токенов:** 1000-5000 на запрос
- **Успешность:** 95%+ успешных запросов

### **Мониторинг:**
- Отслеживание медленных запросов
- Анализ ошибок API
- Статистика использования ключей
- Тренды качества переводов

## 🚀 **Миграции**

### **Создание таблицы prompt_history:**
```bash
cd web_app
source ../.venv/bin/activate
python migrate_prompt_history.py
```

### **Переход на полное удаление глав (опционально):**
```bash
cd web_app
source ../.venv/bin/activate
python migrate_remove_is_active.py
```
**Примечание**: Эта миграция удаляет поле `is_active` из таблицы `chapters` и переключает систему на полное удаление глав.

### **Проверка исправления парсера:**
```bash
cd web_app
source ../.venv/bin/activate
python test_parser_fix.py
```
**Примечание**: Этот тест проверяет, что парсер работает после удаления поля `is_active`. 