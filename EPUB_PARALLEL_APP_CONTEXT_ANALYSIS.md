# Анализ проблемы: Working outside of application context

## Дата: 2025-11-21

## Ошибка

```
Working outside of application context.
This typically means that you attempted to use functionality that needed the current application.
To solve this, set up an application context with app.app_context().
```

## Причина

При добавлении параллельной обработки глав через `ThreadPoolExecutor` новые потоки не имеют контекста Flask приложения, необходимого для работы с SQLAlchemy.

## Архитектура

### 1. Создание EPUBService (views.py:1083)

```python
epub_service = EPUBService(current_app)
```

- ✅ `self.app` устанавливается в конструкторе
- ✅ `current_app` передаётся корректно

### 2. Вызов метода create_bilingual_epub (epub_service.py:531)

```python
def create_bilingual_epub(self, novel_id, chapters, config):
    # ... инициализация ...

    # Строка 597-600: Загрузка глоссария (требует app_context)
    glossary_dict = GlossaryItem.get_chinese_terms_dict(novel_id)

    # Строка 612-619: Параллельная обработка
    def process_chapter(chapter_data):
        with self.app.app_context():  # ← ДОБАВЛЕНО
            return (
                chapter_data['number'],
                self._create_bilingual_chapter_page(...)
            )
```

### 3. Метод _create_bilingual_chapter_page (epub_service.py:918)

```python
def _create_bilingual_chapter_page(self, chapter, nav_css, novel_id, glossary_dict):
    # Строка 961: Запрос к БД (требует app_context)
    novel = Novel.query.get(novel_id)

    # Строка 968: Запрос к БД (требует app_context)
    db_chapter = Chapter.query.filter_by(novel_id=novel_id, ...).first()

    # Строка 978: Сервис выравнивания (может делать запросы к БД)
    alignment_service = BilingualAlignmentService()
    alignments = alignment_service.align_chapter(chapter=db_chapter, ...)
```

## Проблемные места

### ❌ Проблема 1: Загрузка глоссария ВНЕ app_context (строка 602)

```python
glossary_dict = GlossaryItem.get_chinese_terms_dict(novel_id)
```

**Где происходит**: В основном потоке, ДО создания ThreadPoolExecutor

**Статус**: ⚠️ Может работать если вызывается из Flask view (там уже есть app_context)

### ❌ Проблема 2: self.app может быть None

```python
def process_chapter(chapter_data):
    with self.app.app_context():  # ← self.app может быть None!
```

**Причина**: Если EPUBService создан без параметра app

**Проверка**:
```python
def __init__(self, app=None):
    self.app = app  # ← может остаться None!
```

### ❌ Проблема 3: Запросы внутри BilingualAlignmentService

`BilingualAlignmentService` может делать запросы к БД для загрузки/сохранения выравнивания.

## Решение

### Вариант 1: Убедиться что self.app не None ✅ РЕКОМЕНДУЕТСЯ

```python
def create_bilingual_epub(self, novel_id, chapters, config):
    # Проверка наличия app
    if not self.app:
        raise RuntimeError("EPUBService не инициализирован с Flask app")

    # ... остальной код ...
```

### Вариант 2: Получить current_app внутри потока

```python
def process_chapter(chapter_data):
    from flask import current_app
    with current_app.app_context():  # ← Использовать current_app вместо self.app
        return (...)
```

**Проблема**: `current_app` не доступен в новом потоке (thread-local)

### Вариант 3: Передать app как параметр в функцию

```python
def process_chapter(chapter_data, app):
    with app.app_context():
        return (...)

# В ThreadPoolExecutor:
futures = {executor.submit(process_chapter, ch, self.app): ch for ch in chapters}
```

### Вариант 4: Обернуть весь метод в app_context (текущий подход)

```python
def process_chapter(chapter_data):
    with self.app.app_context():
        return (
            chapter_data['number'],
            self._create_bilingual_chapter_page(...)
        )
```

**Статус**: ✅ Должно работать если `self.app` не None

## Рекомендации

### 1. Добавить проверку self.app

```python
def create_bilingual_epub(self, novel_id, chapters, config):
    if not self.app:
        raise RuntimeError(
            "EPUBService не инициализирован с Flask приложением. "
            "Используйте: EPUBService(current_app)"
        )
```

### 2. Добавить логирование для отладки

```python
def process_chapter(chapter_data):
    logger.info(f"🔧 Поток {threading.current_thread().name}: обработка главы {chapter_data['number']}")

    if not self.app:
        logger.error(f"❌ self.app is None!")
        raise RuntimeError("self.app is None")

    with self.app.app_context():
        logger.info(f"✅ App context активен для главы {chapter_data['number']}")
        return (...)
```

### 3. Альтернатива: Использовать @copy_current_request_context

```python
from flask import copy_current_request_context

@copy_current_request_context
def process_chapter(chapter_data):
    # Контекст копируется автоматически
    return (
        chapter_data['number'],
        self._create_bilingual_chapter_page(...)
    )
```

**Проблема**: Работает только для request context, не для app context

## Диагностика

### Шаг 1: Проверить что self.app установлен

```python
# В начале create_bilingual_epub
logger.info(f"DEBUG: self.app = {self.app}")
logger.info(f"DEBUG: self.app type = {type(self.app)}")
```

### Шаг 2: Проверить app_context внутри потока

```python
def process_chapter(chapter_data):
    from flask import has_app_context
    logger.info(f"До app_context: has_app_context() = {has_app_context()}")

    with self.app.app_context():
        logger.info(f"Внутри app_context: has_app_context() = {has_app_context()}")
        return (...)
```

### Шаг 3: Проверить где именно падает

```python
def _create_bilingual_chapter_page(self, ...):
    try:
        logger.info("Попытка Novel.query.get")
        novel = Novel.query.get(novel_id)
        logger.info(f"✅ Novel загружен: {novel}")
    except Exception as e:
        logger.error(f"❌ Ошибка при Novel.query.get: {e}")
        raise
```

## Тестирование

### Тест 1: Последовательная обработка (без потоков)

Временно отключить ThreadPoolExecutor и обработать главы последовательно:

```python
# Вместо ThreadPoolExecutor
for chapter in chapters:
    ch = self._create_bilingual_chapter_page(chapter, nav_css, novel_id, glossary_dict)
    book.add_item(ch)
```

**Ожидание**: Если работает - проблема в threading, если нет - проблема в app_context

### Тест 2: Проверка self.app

```python
def create_bilingual_epub(self, ...):
    assert self.app is not None, "self.app is None"
    assert hasattr(self.app, 'app_context'), "self.app has no app_context"

    # Попробовать создать app_context
    with self.app.app_context():
        logger.info("✅ App context работает в основном потоке")
```

## Решение для текущей проблемы

Нужно добавить проверку и детальное логирование:

```python
def create_bilingual_epub(self, novel_id, chapters, config):
    # 1. Проверка self.app
    if not self.app:
        raise RuntimeError("EPUBService.app is None")

    # 2. Проверка app_context в основном потоке
    from flask import has_app_context
    logger.info(f"🔍 Основной поток: has_app_context = {has_app_context()}")

    # 3. Загрузка глоссария
    with self.app.app_context():
        glossary_dict = GlossaryItem.get_chinese_terms_dict(novel_id)

    # 4. ThreadPoolExecutor с явной проверкой
    def process_chapter(chapter_data):
        import threading
        thread_name = threading.current_thread().name

        logger.info(f"🔧 [{thread_name}] Начало обработки главы {chapter_data['number']}")

        try:
            with self.app.app_context():
                logger.info(f"✅ [{thread_name}] App context активен")
                result = (
                    chapter_data['number'],
                    self._create_bilingual_chapter_page(...)
                )
                logger.info(f"✅ [{thread_name}] Глава обработана")
                return result
        except Exception as e:
            logger.error(f"❌ [{thread_name}] Ошибка: {e}")
            raise
```

## Резюме

**Проблема**: ThreadPoolExecutor создаёт потоки без Flask app context

**Решение**: Оборачивать каждый поток в `with self.app.app_context()`

**Статус**: ✅ Реализовано (строка 615)

**Возможная причина ошибки**: `self.app` может быть `None` или проблема в другом месте

**Следующий шаг**: Добавить детальное логирование для диагностики
