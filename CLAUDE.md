# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Общие команды разработки

### Запуск веб-приложения
```bash
# Рекомендуемый способ
./start_web.sh

# Альтернативные способы
source .venv/bin/activate && python run_web.py
cd web_app && python run.py
```

### Управление зависимостями
```bash
# Установка зависимостей
source .venv/bin/activate
pip install -r requirements.txt
```

### База данных
```bash
# Инициализация БД
cd web_app
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"

# Миграции
python migrate_db.py
python migrate_logs.py
python migrate_prompt_history.py
```

### Тестирование
```bash
# Запуск тестов
pytest

# Тестирование системы парсеров
python test_parser_system.py

# Тестирование веб-интеграции
python test_web_integration.py

# Запуск конкретного теста
pytest test_parser.py
pytest test_translator.py
```

### Код-стиль и форматирование
```bash
# Форматирование кода
black .

# Проверка стиля
flake8
```

## Архитектура проекта

### Основная бизнес-логика

1. **Парсинг глав** (`1_parser_selenium.py`):
   - Использует Selenium для парсинга сайтов с JavaScript
   - Сохраняет результаты в БД и файлы JSON в `parsed_chapters/`
   - Поддерживает пагинацию и JavaScript-контент

2. **Перевод** (`2_translator_improved.py`):
   - Интеграция с Google Gemini, OpenAI GPT и Claude
   - Ротация API ключей для балансировки нагрузки
   - Сохранение переводов в `translations/` и проблемных в `translations_problems/`

3. **Редактирование** (`3_editor.py`):
   - Интерактивное редактирование переводов
   - Сохранение в `edited_translations/` с метаданными

4. **Генерация EPUB** (`4_epub_generator.py`):
   - Создание EPUB из отредактированных переводов
   - Результаты в `epub_output/`

### Веб-приложение Flask

Структура Flask-приложения следует паттерну MVC:

- **Модели** (`web_app/app/models/`): SQLAlchemy модели для Novel, Chapter, Translation, Task, Settings
- **Сервисы** (`web_app/app/services/`): Бизнес-логика для парсинга, перевода, редактирования, генерации EPUB
- **API** (`web_app/app/api/`): REST API для взаимодействия с фронтендом
- **Представления** (`web_app/app/views.py`): Контроллеры Flask

### Асинхронные задачи

Используется Celery + Redis для фоновых задач:
- Парсинг глав
- Перевод текста
- Генерация EPUB

### База данных

SQLite база данных с таблицами:
- `novels` - информация о новеллах
- `chapters` - главы новелл
- `translations` - переводы глав
- `tasks` - асинхронные задачи
- `system_settings` - настройки системы (API ключи, параметры)
- `prompt_templates` - шаблоны промптов для перевода
- `glossary` - глоссарий терминов

### WebSocket интеграция

Используется Flask-SocketIO для:
- Консоли в реальном времени
- Обновления статуса задач
- Интерактивного редактирования

## Важные детали реализации

1. **Обработка ошибок API**: Автоматическая ротация ключей при ошибках квоты
2. **Статусы глав**: `pending`, `parsing`, `parsed`, `translating`, `translated`, `editing`, `edited`, `error`
3. **Логирование**: Ротируемые логи в `web_app/logs/app.log`
4. **Безопасность**: API ключи хранятся в БД, не в коде
5. **Кэширование**: 15-минутный кэш для веб-запросов

## Система парсеров (Новая архитектура)

### Структура парсеров
```
parsers/
├── __init__.py                 # Основные экспорты
├── base/
│   ├── __init__.py
│   └── base_parser.py         # Базовый класс BaseParser
├── sources/
│   ├── __init__.py
│   └── qidian_parser.py       # Парсер для Qidian.com
├── parser_factory.py          # Фабрика парсеров
└── parser_integration.py      # Интеграция с веб-приложением
```

### Использование системы парсеров
```python
from parsers import create_parser, create_parser_from_url, detect_source

# Создание парсера по типу источника
parser = create_parser('qidian')

# Автоматическое создание парсера по URL
parser = create_parser_from_url('https://www.qidian.com/book/1209977/')

# Автоопределение источника
source = detect_source('https://www.qidian.com/book/1209977/')

# Скачивание книги
results = parser.download_book(url, './output', chapter_limit=5)
```

### Поддерживаемые источники
- **Qidian (起点中文网)**: Китайская платформа веб-новелл
  - Поддержка мобильной версии (обход защиты)
  - Автоматическое определение по URL
  - Оптимизированные задержки для избежания блокировок

### Веб-интерфейс
- Автоматическое определение источника по URL
- Динамические описания источников
- Валидация соответствия URL и типа источника
- Fallback режим для совместимости

## Полезные пути

- Веб-интерфейс: `http://localhost:5001`
- База данных: `web_app/instance/novel_translator.db`
- Логи: `web_app/logs/app.log`
- Переводы: `translations/`, `edited_translations/`
- EPUB: `epub_output/`
- Парсеры: `parsers/`
- Тестовые данные Qidian: `qidian_parsed/`