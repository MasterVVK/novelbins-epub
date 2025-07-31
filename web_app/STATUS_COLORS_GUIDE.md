# Руководство по использованию системы цветов статусов

## Обзор

Централизованная система цветов статусов обеспечивает единообразие и семантическую ясность цветового оформления во всем приложении web_app.

## Структура системы

### 1. Серверная часть (Python)

#### Основной модуль: `app/utils/status_colors.py`
```python
from app.utils.status_colors import status_colors

# Получение цвета для статуса новеллы
color = status_colors.get_novel_status_color('completed')  # 'success'

# Получение цвета для статуса главы
color = status_colors.get_chapter_status_color('translated')  # 'primary'

# Универсальный метод
color = status_colors.get_status_color('completed', 'novel')  # 'success'
```

#### Jinja2 фильтры: `app/utils/template_filters.py`
```html
<!-- В шаблонах -->
<span class="{{ novel.status|status_badge_class('novel') }}">
    <i class="{{ novel.status|status_icon('novel') }}"></i>
    {{ novel.status|status_text('novel') }}
</span>
```

### 2. Клиентская часть (JavaScript)

#### Модуль: `app/static/js/status_colors.js`
```javascript
// Получение цвета для статуса
const color = StatusColors.getNovelStatusColor('completed');  // 'success'

// Создание HTML badge
const badge = StatusColors.createStatusBadge('running', 'task_status');

// Универсальный метод
const color = StatusColors.getStatusColor('failed', 'task_status');  // 'danger'
```

## Цветовая схема

### Статусы процесса
- `pending` → `secondary` (серый) - ожидание
- `running` → `warning` (желтый) - выполняется
- `completed` → `success` (зеленый) - завершено
- `failed` → `danger` (красный) - ошибка

### Статусы контента
- `parsed` → `info` (синий) - распарсено
- `translated` → `primary` (темно-синий) - переведено
- `edited` → `success` (зеленый) - отредактировано
- `error` → `danger` (красный) - ошибка

### Типы задач
- `parse` → `info` (синий) - парсинг
- `translate` → `primary` (темно-синий) - перевод
- `edit` → `warning` (желтый) - редактура
- `generate_epub` → `dark` (темно-серый) - генерация EPUB

### Специальные статусы
- `deleted` → `danger` (красный) - удалено
- `is_default` → `success` (зеленый) - по умолчанию
- `is_active` → `success` (зеленый) / `secondary` (серый) - активен/неактивен

### Уровни логов
- `INFO` → `info` (синий) - информация
- `WARNING` → `warning` (желтый) - предупреждение
- `ERROR` → `danger` (красный) - ошибка

## Использование в шаблонах

### Базовое использование
```html
<!-- Статус новеллы -->
<span class="{{ novel.status|status_badge_class('novel') }}">
    <i class="{{ novel.status|status_icon('novel') }}"></i>
    {{ novel.status|status_text('novel') }}
</span>

<!-- Статус главы -->
<span class="{{ chapter.status|status_badge_class('chapter') }}">
    <i class="{{ chapter.status|status_icon('chapter') }}"></i>
    {{ chapter.status|status_text('chapter') }}
</span>

<!-- Статус задачи -->
<span class="{{ task.status|status_badge_class('task_status') }}">
    <i class="{{ task.status|status_icon('task_status') }}"></i>
    {{ task.status|status_text('task_status') }}
</span>

<!-- Тип задачи -->
<span class="{{ task.task_type|status_badge_class('task_type') }}">
    <i class="{{ task.task_type|status_icon('task_type') }}"></i>
    {{ task.task_type|status_text('task_type') }}
</span>
```

### Доступные фильтры
- `status_color(entity_type, **kwargs)` - получить только цвет
- `status_badge_class(entity_type, **kwargs)` - получить полный класс badge
- `status_icon(entity_type)` - получить иконку
- `status_text(entity_type)` - получить человекочитаемый текст
- `novel_status_color()` - цвет статуса новеллы
- `chapter_status_color()` - цвет статуса главы
- `task_status_color()` - цвет статуса задачи
- `task_type_color()` - цвет типа задачи
- `log_level_color()` - цвет уровня лога
- `prompt_template_status_color()` - цвет статуса шаблона промпта

## Использование в JavaScript

### Подключение
```html
<script src="{{ url_for('static', filename='js/status_colors.js') }}"></script>
```

### Базовое использование
```javascript
// Получение цвета
const color = StatusColors.getNovelStatusColor('completed');

// Создание HTML badge
const badge = StatusColors.createStatusBadge('running', 'task_status');

// Универсальный метод
const color = StatusColors.getStatusColor('failed', 'task_status');
```

### Доступные методы
- `getNovelStatusColor(status)` - цвет статуса новеллы
- `getChapterStatusColor(status)` - цвет статуса главы
- `getTaskStatusColor(status)` - цвет статуса задачи
- `getTaskTypeColor(taskType)` - цвет типа задачи
- `getLogLevelColor(level)` - цвет уровня лога
- `getStatusIcon(status, entityType)` - иконка статуса
- `getStatusText(status, entityType)` - текст статуса
- `createStatusBadge(status, entityType)` - создать HTML badge
- `getStatusColor(status, entityType)` - универсальный метод

## Добавление новых статусов

### 1. Обновить серверную часть
```python
# В app/utils/status_colors.py
class StatusColors:
    # Добавить новую константу
    NEW_STATUS = 'info'  # или другой цвет
    
    @classmethod
    def get_new_entity_status_color(cls, status: str) -> str:
        color_map = {
            'new_status': cls.NEW_STATUS,
            # другие статусы...
        }
        return color_map.get(status, cls.PROCESS_PENDING)
```

### 2. Обновить клиентскую часть
```javascript
// В app/static/js/status_colors.js
const StatusColors = {
    // Добавить новую константу
    NEW_STATUS: 'info',
    
    getNewEntityStatusColor(status) {
        const colorMap = {
            'new_status': this.NEW_STATUS,
            // другие статусы...
        };
        return colorMap[status] || this.PROCESS_PENDING;
    }
};
```

### 3. Добавить фильтр (если нужно)
```python
# В app/utils/template_filters.py
@app.template_filter('new_entity_status_color')
def new_entity_status_color_filter(status):
    return status_colors.get_new_entity_status_color(status)
```

## Принципы использования

### 1. Семантическая ясность
- Цвет должен отражать значение статуса
- Используйте интуитивно понятные цвета

### 2. Единообразие
- Одинаковые статусы должны иметь одинаковые цвета
- Используйте централизованную систему

### 3. Доступность
- Цвета должны быть различимы для всех пользователей
- Не полагайтесь только на цвет для передачи информации

### 4. Консистентность
- Используйте одни и те же цвета для одинаковых понятий
- Следуйте установленной схеме

## Примеры миграции

### До (старый способ)
```html
<span class="badge bg-{{ 'success' if novel.status == 'completed' else 'warning' if novel.status == 'translating' else 'info' }}">
    {{ novel.status }}
</span>
```

### После (новый способ)
```html
<span class="{{ novel.status|status_badge_class('novel') }}">
    <i class="{{ novel.status|status_icon('novel') }}"></i>
    {{ novel.status|status_text('novel') }}
</span>
```

## Тестирование

### Проверка всех статусов
```python
# Тестовый скрипт
from app.utils.status_colors import status_colors

test_statuses = {
    'novel': ['pending', 'parsing', 'translating', 'editing', 'completed', 'deleted'],
    'chapter': ['pending', 'parsed', 'translated', 'edited', 'error'],
    'task_status': ['pending', 'running', 'completed', 'failed'],
    'task_type': ['parse', 'translate', 'edit', 'generate_epub']
}

for entity_type, statuses in test_statuses.items():
    print(f"\n{entity_type}:")
    for status in statuses:
        color = status_colors.get_status_color(status, entity_type)
        print(f"  {status} → {color}")
```

## Заключение

Централизованная система цветов статусов обеспечивает:
- Единообразие во всем приложении
- Легкость поддержки и обновления
- Семантическую ясность
- Удобство использования для разработчиков

Всегда используйте эту систему вместо inline логики цветов в шаблонах и JavaScript коде. 