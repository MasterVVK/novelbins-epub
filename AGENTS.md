# Анализ Репозитория Translation System

## Обзор Проекта

### Назначение и Цели
Это веб-приложение для автоматического перевода китайских веб-новелл (сянся/фэнтези жанра) с использованием искусственного интеллекта. Система разработана для:

- Парсинга глав с сайтов новелл (primarily novelbins.com и czbooks.net)
- Перевода с китайского на русский с учетом жанровой специфики и терминологии
- Постобработки перевода с использованием многоэтапной редактуры
- Создания готовых EPUB файлов для чтения
- Управления глоссарием для терминологической последовательности

### Основные Технологии
- **Backend**: Flask 2.x, SQLAlchemy, Celery, Redis
- **Database**: SQLite с миграциями Alembic
- **AI Models**: Gemini 2.5, OpenAI, Ollama, Claude (универсальный адаптер)
- **Web Scraping**: Selenium WebDriver с обходом Cloudflare
- **Task Queue**: Celery для фоновой обработки
- **Frontend**: Jinja2 шаблоны, Bootstrap 5, Socket.IO для real-time updates
- **EPUB**: ebooklib для генерации готовых файлов

## Архитектура

### Основные Компоненты

1. **Web Application** (`web_app/`)
   - Flask приложение с модульной архитектурой
   - REST API для управления новеллами, главами и переводами
   - WebSocket для real-time обновлений прогресса
   - Система авторизации и управления пользователями

2. **Translation Pipeline** (`web_app/app/services/`)
   - **TranslatorService**: основной сервис перевода с поддержкой шаблонов промптов
   - **EditorService**: многоэтапная редактура перевода (анализ → стиль → диалоги → полировка)
   - **GlossaryService**: управление терминами и обеспечение консистентности
   - **ParserService**: интеграция парсеров для различных источников

3. **Background Tasks** (`web_app/app/celery_tasks.py`)
   - Фоновый парсинг глав с отменой задач и прогрессом
   - Параллельные переводы с использованием Celery
   - Автоматическое управление API ключами и лимитами

4. **Universal LLM Adapter** (`web_app/app/services/universal_llm_translator.py`)
   - Единый интерфейс для различных LLM (Gemini, OpenAI, Claude, Ollama)
   - Интеллектуальная ротация API ключей и обработка rate limiting
   - Конфигурация температуры и параметров для каждой модели

### Поток Данных
1. **Парсинг**: URL → Parser → DB (parsed chapters)
2. **Перевод**: DB → ContextBuilder → LLM → DB (translations)
3. **Редактура**: DB → MultiStageEditor → DB (edited chapters)
4. **Export**: DB → EPUBGenerator → epub file

## Структура Директорий

```
web_app/
├── app/                          # Основное Flask приложение
│   ├── api/                      # REST API endpoints
│   │   ├── chapters.py          # Управление главами
│   │   ├── glossary.py          # Работа с глоссарием
│   │   ├── novels.py            # Управление новеллами
│   │   └── tasks.py             # Управление Celery задачами
│   ├── models/                   # SQLAlchemy модели
│   │   ├── ai_model.py          # Конфигурация AI моделей
│   │   ├── chapter.py           # Модель главы
│   │   ├── glossary.py          # Модель терминов глоссария
│   │   ├── novel.py             # Модель новеллы
│   │   └── prompt_template.py   # Шаблоны промптов
│   ├── services/                 # Бизнес-логика
│   │   ├── ai_adapter_service.py # Адаптер для AI моделей
│   │   ├── editor_service.py    # Многоэтапная редактура
│   │   ├── glossary_service.py  # Управление глоссарием
│   │   ├── translator_service.py# Перевод текста
│   │   └── universal_llm_translator.py # Универсальный LLM адаптер
│   ├── templates/               # HTML шаблоны Jinja2
│   ├── static/                  # CSS, JS, изображения
│   └── utils/                   # Вспомогательные функции
├── config/                      # Конфигурация Flask
├── migrations/                  # Alembic миграции
└── run.py                      # Точка входа приложения

parsers/                         # Система парсеров
├── base/base_parser.py         # Базовый абстрактный парсер
├── sources/czbooks_parser.py   # Парсер для czbooks.net
└── sources/qidian_parser.py    # Парсер для qidian

```

## Точки Входа

### Основные скрипты
- `web_app/run.py` - Запуск Flask сервера (port 5001)
- `web_app/start_celery_worker.sh` - Запуск Celery worker для фоновых задач
- `web_app/init_db.py` - Инициализация базы данных

### API Endpoints
- `/api/novels/` - CRUD операции с новеллами
- `/api/chapters/<id>/translate` - Запуск перевода главы
- `/api/tasks/<id>/status` - Проверка статуса задачи
- `/api/glossary/` - Управление глоссарием

### Шаблоны URL
- `/novels/` - Список новелл
- `/novel/<id>/` - Детали новеллы
- `/novel/<id>/chapters/` - Управление главами
- `/console/` - Консоль для real-time логов

## Тестирование и Локальная Разработка

### Настройка Окружения
```bash
# Установка зависимостей
pip install -r web_app/requirements.txt  # если есть

# Настройка переменных окружения
export DATABASE_URL="sqlite:///translations.db"
export CELERY_BROKER_URL="redis://localhost:6379/1"
export SECRET_KEY="your-secret-key"
export GEMINI_API_KEYS="key1,key2,key3"

# Запуск Redis (для Celery)
redis-server
```

### Запуск Сервисов
```bash
# 1. Запуск Flask приложения
cd web_app && python run.py

# 2. Запуск Celery worker (в отдельном терминале)
cd web_app && ./start_celery_worker.sh

# 3. Инициализация базы данных (один раз)
flask init-db
```

### Тестирование
```bash
# Проверка подключения к API
python -c "from app.services.translator_service import LLMTranslator; print('OK')"

# Тест парсинга (если доступен)
curl http://localhost:5001/api/novels/parse -X POST \
   -H "Content-Type: application/json" \
   -d '{"url": "https://czbooks.net/n/12345"}'
```

## Код Стайл и Линтинг

### Правила кода:
- **Импорты**: сначала стандартные библиотеки, затем сторонние, затем локальные
- **Оформление**: использование f-строк, type hints для сложных функций
- **Ошибки**: подробное логирование с контекстом (novel_id, chapter_id во всех сервисах)
- **БД**: использование SQLAlchemy ORM, избегать raw SQL
- **Config**: все настройки в Config классе, не хардкодить

### Рекомендации:
- Проверять наличие моделей и терминов перед использованием
- Всегда использовать LogService для логирования операций
- Обрабатывать edge cases (пустой текст, заблокированный контент, таймауты)
- Проверка качества перевода через validation перед сохранением
- Использование транзакций SQLAlchemy для batch операций