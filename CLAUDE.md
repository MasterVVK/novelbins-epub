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
  - **Сервисы редактуры**:
    - `original_aware_editor_service.py`: **ОСНОВНОЙ ИСПОЛЬЗУЕМЫЙ** - редактура с оригинальным текстом и глоссарием
    - `glossary_aware_editor_service.py`: Базовый сервис редактуры с учетом глоссария (родительский класс)
    - `editor_service.py`: Многоэтапная редактура (analysis → style → dialogue → polish)
    - `parallel_editor_service.py`: Устаревший, НЕ ИСПОЛЬЗУЕТСЯ (имел баг с одинаковым результатом)
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

**Архитектура очередей**:
- **Одна общая очередь**: `czbooks_queue` для всех задач (парсинг, перевод, редактура)
- **Один worker**: `--concurrency=1 --pool=solo` из-за ограничений Selenium
- **Последовательное выполнение**: Все задачи выполняются строго по очереди
- **ВАЖНО**:
  - ❌ Парсинг и редактура одновременно НЕ работают
  - ❌ Редактура разных новелл одновременно НЕ работает
  - ✅ Задачи выполняются последовательно в порядке поступления

**Задачи**:
- **Парсинг глав** (`parsing.py:55`):
  - Очередь: `czbooks_queue`
  - С отслеживанием прогресса и поддержкой отмены
  - Требует Xvfb для Selenium (non-headless Chrome)

- **Параллельный перевод**:
  - Несколько глав одновременно внутри одной задачи

- **Параллельная редактура** (`celery_tasks.py:267-492`, `views.py:813`):
  - Очередь: `czbooks_queue`
  - Использует `ThreadPoolExecutor` для параллельной обработки **глав одной новеллы**
  - Каждый поток создает свой Flask `app_context()` для изоляции сессий БД
  - Настраиваемое количество потоков через `novel.config['editing_threads']` (по умолчанию: 3, рекомендуется 2-5)
  - **Защита от дублирования**: Проверка `chapter.status == 'edited'` в начале каждого потока
  - **Thread-safe обновления**: Использование `Lock()` для безопасного обновления счетчиков
  - **Глобальная переменная отмены**: `_cancel_requested` (общая для всех задач в worker'е)
  - **Отмена задач**:
    - Проверка статуса между главами через `novel.status == 'editing_cancelled'`
    - Отмена через `celery.control.revoke(task_id, terminate=True, signal='SIGTERM')` (`editing.py:33`)
    - API endpoint: `POST /api/novels/<id>/edit/cancel`
  - **Используемый сервис**: `OriginalAwareEditorService` (с оригинальным текстом и глоссарием)

- **Отмена задач**: Через сигналы SIGTERM с graceful shutdown
- Использует отдельную Redis БД (DB 1) для изоляции

**Модель Novel** (`app/models/novel.py`):
- `editing_task_id`: ID активной Celery задачи редактуры (аналог `parsing_task_id`)
- `config['editing_threads']`: Количество параллельных потоков редактуры (1-10, рекомендуется 2-5)
- `edited_chapters`: Счетчик успешно отредактированных глав (обновляется в реальном времени)

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

### Editing System Architecture

**OriginalAwareEditorService** - основной сервис редактуры (`app/services/original_aware_editor_service.py:36-145`):

Этапы редактуры главы:
1. **Загрузка данных** (строки 40-70):
   - Проверка наличия `original_text` (китайский оригинал)
   - Проверка наличия `translated_text` (русский перевод)
   - Загрузка приоритезированного глоссария через `_load_prioritized_glossary()`
   - Подсчет терминов во всех категориях глоссария

2. **Анализ с оригиналом** (строки 75-85):
   - Сравнение перевода с оригинальным текстом
   - Выявление несоответствий смысла
   - Проверка точности передачи ключевых моментов
   - Генерация стратегии исправления

3. **Исправление с учетом оригинала** (строки 86-95):
   - Корректировка неточностей перевода
   - Улучшение передачи смысла оригинала
   - Сохранение терминологии из глоссария

4. **Улучшение стиля** (строки 96-106):
   - Полировка текста для читабельности
   - Улучшение литературного стиля
   - Сохранение точности перевода

5. **Сохранение результата** (строки 107-130):
   - Обновление `chapter.edited_text`
   - Установка `chapter.status = 'edited'`
   - Логирование времени редактуры и качества

**Методы редактуры**:
- `analyze_with_original()`: Анализ качества перевода через сравнение с оригиналом
- `fix_with_original()`: Исправление ошибок с использованием оригинального текста
- `polish_with_original()`: Финальная полировка стиля с сохранением точности

**Используемые промпт-шаблоны** (`app/services/prompt_template_service.py`):
- `analyze_with_original_prompt`: Для анализа соответствия оригиналу
- `fix_with_original_prompt`: Для исправления с учетом оригинала
- `polish_with_original_prompt`: Для финальной полировки

**Интеграция с глоссарием**:
- Наследуется от `GlossaryAwareEditorService`
- Автоматическое применение терминов из глоссария
- Проверка консистентности терминологии
- Приоритезация: специфичные термины новеллы → общие термины жанра

### Logging System

Централизованное логирование через `LogService`:
- Rotational file logs (`logs/app.log`)
- Console output для разработки
- **Контекстное логирование** с префиксом `[Novel:ID, Ch:NUM]` во всех операциях:
  - Логи редактуры (`celery_tasks.py:329, 348, 360, 379, 384, 390, 418, 449, 466, 480, 489`)
  - Логи OriginalAwareEditorService (`original_aware_editor_service.py:41, 131, 136`)
  - Логи загрузки глоссария (`original_aware_editor_service.py:69`, `glossary_aware_editor_service.py:38`)
  - **Логи Ollama запросов** (`ai_adapter_service.py:339-346`):
    - Передача `chapter_id` через `AIAdapterService.__init__(chapter_id=...)`
    - Загрузка главы для получения `novel_id` и `chapter_number`
    - Формат: `[Novel:11, Ch:104] Ollama запрос: glm-4.6:cloud | Temperature: 0.5 | Num ctx: 10,723 | ...`
