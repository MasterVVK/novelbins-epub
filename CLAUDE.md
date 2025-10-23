# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Web-приложение на Flask для автоматического перевода китайских веб-новелл (преимущественно жанр сянся/фэнтези) с использованием AI моделей. Система включает парсинг глав с различных источников, перевод с китайского на русский, многоэтапную редактуру и генерацию EPUB файлов.

## Common Development Commands

### Web Application
```bash
# Запуск веб-приложения (основной способ)
python run_web.py                    # из корня проекта
# или
cd web_app && python run.py         # из директории web_app

# Приложение запускается на http://0.0.0.0:5001

# Инициализация базы данных (при первом запуске)
flask --app run_web init-db

# Миграции базы данных
cd web_app
flask db migrate -m "описание изменений"
flask db upgrade
```

### Celery Background Tasks
```bash
# Запуск Celery worker (требуется Redis и Xvfb для парсинга czbooks)
cd web_app
./start_celery_worker.sh

# Проверка статуса Redis
redis-cli ping

# Запуск Redis (если не запущен)
sudo systemctl start redis-server
```

## Architecture Overview

### Модульная Архитектура Flask

Приложение использует фабрику приложений (`create_app()`) с разделением на blueprints:

- **API Endpoints** (`web_app/app/api/`): REST API для управления
  - `novels.py`: CRUD операции с новеллами
  - `chapters.py`: Управление главами, запуск переводов
  - `glossary.py`: Работа с терминологическим глоссарием
  - `tasks.py`: Мониторинг Celery задач

- **Models** (`web_app/app/models/`): SQLAlchemy модели
  - `novel.py`: Модель новеллы с метаданными
  - `chapter.py`: Главы с оригиналом и переводом
  - `ai_model.py`: Конфигурация AI моделей с поддержкой нескольких провайдеров
  - `glossary.py`: Терминологический глоссарий для консистентности
  - `prompt_template.py`: Шаблоны промптов для переводов

- **Services** (`web_app/app/services/`): Бизнес-логика
  - `universal_llm_translator.py`: Универсальный переводчик с поддержкой Gemini, OpenAI, Claude, Ollama
  - `translator_service.py`: Сервис перевода с использованием промпт-шаблонов
  - `editor_service.py`: Многоэтапная редактура (analysis → style → dialogue → polish)
  - `glossary_service.py`: Управление глоссарием и извлечение терминов
  - `parser_service.py`: Интеграция парсеров для различных источников
  - `ai_adapter_service.py`: Адаптер для унифицированной работы с AI провайдерами

### Parser System

Система парсеров с фабричным паттерном (`parsers/parser_factory.py`):

- **Base Parser** (`parsers/base/base_parser.py`): Абстрактный класс с общим интерфейсом
- **Source Parsers** (`parsers/sources/`):
  - `czbooks_parser.py`: Парсер для czbooks.net (требует Selenium + Xvfb)
  - `qidian_parser.py`: Парсер для qidian.com
  - `epub_parser.py`: Импорт из EPUB файлов

Парсеры поддерживают:
- Автоопределение источника по URL
- SOCKS5 прокси для обхода блокировок
- Cookie-based аутентификацию
- Headless/non-headless режимы (czbooks требует non-headless)

### AI Translation Pipeline

1. **Context Building**: Сбор контекста из предыдущих глав + применение глоссария
2. **LLM Translation**: Перевод через универсальный адаптер с ротацией API ключей
3. **Multi-Stage Editing**: Последовательная редактура для улучшения качества
4. **Quality Scoring**: Автоматическая оценка качества перевода

**Ollama параметры** (`ai_adapter_service.py:303-326`):
- **Оценка токенов**: Адаптивная на основе языка текста
  - Китайский: 1.5 символа/токен
  - Русский: 2.5 символа/токен
  - Английский: 4.0 символа/токен
- **num_ctx**: `prompt_length × 1.2` (промпт + 20% буфер, минимум 2048)
- **num_predict**: `num_ctx × 2` (но не больше max_output_tokens модели)
- **Таймаут**: 1200 секунд (20 минут) для обработки больших моделей
- **Повторы при ошибках** (`universal_llm_translator.py:230-294`):
  - timeout, upstream_timeout, upstream_error, server_error: 2 попытки (30 сек, 5 мин)
  - rate_limit: 4 попытки (5 мин, 10 мин, 20 мин, 30 мин)
- Формула оптимизирована для переводов китайский→русский

### Background Task Queue

Celery с Redis для фоновой обработки (`web_app/app/celery_tasks.py`):
- **Парсинг глав**: С отслеживанием прогресса и поддержкой отмены
- **Параллельный перевод**: Несколько глав одновременно
- **Параллельная редактура** (`celery_tasks.py:268-417`):
  - Обработка глав батчами через `ParallelEditorService`
  - Настраиваемое количество потоков через `novel.config['editing_threads']` (по умолчанию: 3)
  - Многоуровневая отмена: между батчами, между главами в батче, в начале обработки главы
  - API endpoint: `POST /api/novels/<id>/edit/cancel`
- **Отмена задач**: Через сигналы SIGTERM с graceful shutdown
- Использует отдельную Redis БД (DB 1) для изоляции

**Модель Novel** (`app/models/novel.py`):
- `editing_task_id`: ID активной Celery задачи редактуры (аналог `parsing_task_id`)
- `config['editing_threads']`: Количество параллельных потоков редактуры (1-10, рекомендуется 2-5)

### Configuration System

Конфигурация через классы (`web_app/config/__init__.py`):
- `DevelopmentConfig`: DEBUG режим, подробное логирование
- `ProductionConfig`: Оптимизирован для production
- `TestingConfig`: In-memory база для тестов

Переменные окружения из `.env`:
- `GEMINI_API_KEYS`: Список Gemini API ключей через запятую
- `CELERY_BROKER_URL`: Redis URL для Celery (по умолчанию DB 1)
- `DATABASE_URL`: SQLite путь к основной базе
- `PROXY_URL`: SOCKS5 прокси для парсинга

### Key Integration Points

**UniversalLLMTranslator с ротацией ключей**:
- Автоматическое переключение между Gemini API ключами при rate limiting
- Отслеживание failed ключей и попытки восстановления
- Поддержка сохранения истории промптов для отладки

**Parser Factory автоопределение**:
- Регистрация парсеров с URL паттернами
- `create_parser_from_url()` автоматически выбирает правильный парсер
- Легкое добавление новых парсеров через `register_parser()`

**Celery Integration**:
- Flask app context для всех задач
- Soft/hard time limits для предотвращения зависаний
- Обработка SIGTERM для корректной отмены задач
- Real-time обновления через SocketIO

### Logging System

Централизованное логирование через `LogService`:
- Rotational file logs (`logs/app.log`)
- Console output для разработки
- Контекстное логирование (novel_id, chapter_id во всех операциях)
