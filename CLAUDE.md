# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Auto-Commit Policy

**ВАЖНО**: После каждого изменения кода (Edit, Write) автоматически делай git commit:
```bash
git add <изменённые файлы>
git commit -m "Краткое описание изменения

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```
Push НЕ делать — пользователь делает push сам.

## Project Overview

Web-приложение на Flask для автоматического перевода китайских веб-новелл (преимущественно жанр сянся/фэнтези) с использованием AI моделей. Система включает парсинг глав с различных источников, перевод с китайского на русский, многоэтапную редактуру и генерацию EPUB файлов.

### Cloudflare Turnstile Solver

**Автоматическое решение Cloudflare Turnstile через Qwen3-VL vision модель (локально через Ollama)**

- **Модель**: `qwen3-vl:8b` (6GB) или `qwen3-vl:32b` (21GB)
- **Интеграция**: `parsers/sources/czbooks_parser.py:478-520`
- **Сервис**: `web_app/app/services/cloudflare_solver_ollama.py`
- **Конфигурация**: `.env` → `CLOUDFLARE_SOLVER_ENABLED=true`

При обнаружении Cloudflare: автоматическое решение (3 попытки) → VNC fallback.

## Common Development Commands

### Web Application
```bash
python run_web.py                    # Запуск на http://0.0.0.0:5001
flask --app run_web init-db          # Инициализация БД
cd web_app && flask db migrate -m "описание" && flask db upgrade  # Миграции
```

### Celery Background Tasks
```bash
cd web_app && ./start_celery_worker.sh  # Требуется Redis + Xvfb
redis-cli ping                           # Проверка Redis
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
  - `universal_llm_translator.py`: Универсальный переводчик (Gemini, OpenAI, Claude, Ollama)
  - `translator_service.py`: Сервис перевода с промпт-шаблонами
  - `original_aware_editor_service.py`: **ОСНОВНОЙ** - редактура с оригиналом и глоссарием
  - `glossary_service.py`: Управление глоссарием
  - `parser_service.py`: Интеграция парсеров
  - `ai_adapter_service.py`: Адаптер для AI провайдеров

### Parser System

Система парсеров (`parsers/parser_factory.py`):
- `czbooks_parser.py`: czbooks.net (Selenium + Xvfb, non-headless)
- `qidian_parser.py`: qidian.com
- `epub_parser.py`: Импорт из EPUB

Поддерживают: автоопределение по URL, SOCKS5 прокси, Cookie-auth.

### AI Translation Pipeline

1. **Context Building**: Контекст из предыдущих глав + глоссарий
2. **LLM Translation**: Перевод с ротацией API ключей
3. **Multi-Stage Editing**: Последовательная редактура
4. **Quality Scoring**: Оценка качества

**Контекстная фильтрация глоссария** (`_format_context_glossary()`):
- В промпт включаются только термины, присутствующие в оригинальном тексте главы
- Экономия токенов: 98.5% (51,731 → 788 токенов на главу)
- Применяется в: переводе, редактуре, генерации summary, извлечении терминов

**Ollama параметры** (`ai_adapter_service.py:303-326`):
- Токены: китайский 1.5 сим/токен, русский 2.5, английский 4.0
- `num_ctx`: `prompt_length × 1.2` (минимум 2048)
- Таймаут: 1200 сек (20 мин)
- Повторы: timeout 2×, rate_limit 4×

### Background Task Queue

Celery с Redis (`web_app/app/celery_tasks.py`):
- **Два worker'а:**
  - Parsing worker (`start_celery_worker.sh`): `--pool=solo --concurrency=1 --queues=czbooks_queue` (Selenium + Xvfb)
  - LLM worker (`start_llm_worker.sh`): `--pool=prefork --concurrency=4 --queues=llm_queue` (перевод, редактура, сопоставление, EPUB)
- **Per-novel блокировка**: `get_active_task_for_novel()` — только 1 задача на новеллу, разные новеллы параллельно
- **БД**: PostgreSQL 18.0 (MVCC, без блокировок)

**Задачи**:
- Парсинг глав с отслеживанием прогресса
- Параллельный перевод внутри задачи
- Параллельная редактура через `ThreadPoolExecutor` (настройка `editing_threads`: 2-5)
- Отмена через SIGTERM

**Модель Novel**:
- `editing_task_id`: ID активной задачи редактуры
- `config['editing_threads']`: Потоки редактуры (1-10)
- `edited_chapters`: Счетчик отредактированных глав

### Configuration System

Конфигурация (`web_app/config/__init__.py`): `DevelopmentConfig`, `ProductionConfig`, `TestingConfig`

**Переменные `.env`**:
- `GEMINI_API_KEYS`: Ключи через запятую
- `CELERY_BROKER_URL`: Redis URL (DB 1)
- `DATABASE_URL`: PostgreSQL connection string
- `PROXY_URL`: SOCKS5 прокси

**База данных PostgreSQL:**
```bash
PGPASSWORD='novelbins_strong_pass_2025' psql -U novelbins_user -d novelbins_epub -h localhost
```
Таблицы: novels, chapters, ai_models, glossary_items, prompt_templates, tasks, log_entries, bilingual_alignments, bilingual_prompt_templates

### Editing System Architecture

**OriginalAwareEditorService** (`app/services/original_aware_editor_service.py`):

Этапы редактуры:
1. Загрузка данных + глоссарий (контекстная фильтрация)
2. Анализ с оригиналом (сравнение, выявление несоответствий)
3. Исправление с учетом оригинала
4. Улучшение стиля
5. Сохранение (`chapter.edited_text`, `status='edited'`)

**Контекстная фильтрация глоссария**: Метод `_format_context_glossary()` включает в промпт только термины из `original_text`. Заменил старый `_format_entire_glossary()` с жёсткими лимитами (50 characters, 30 locations).

**Промпт-шаблоны**: `analyze_with_original_prompt`, `fix_with_original_prompt`, `polish_with_original_prompt`

### Logging System

`LogService` с контекстным логированием `[Novel:ID, Ch:NUM]`:
- Rotational file logs (`logs/app.log`)
- Console output для разработки

---

## Bilingual Alignment System

> **Полная документация**: [docs/BILINGUAL_ALIGNMENT.md](docs/BILINGUAL_ALIGNMENT.md)

**Система AI-сопоставления китайского оригинала и русского перевода для двуязычных EPUB**

### Ключевые компоненты

| Компонент | Путь | Назначение |
|-----------|------|------------|
| **BilingualAlignment** | `models/bilingual_alignment.py` | Результаты сопоставления (JSON массив пар) |
| **BilingualPromptTemplate** | `models/bilingual_prompt_template.py` | Шаблоны промптов для LLM |
| **BilingualAlignmentService** | `services/bilingual_alignment_service.py` | AI-сопоставление текстов |
| **align_novel_chapters_task** | `celery_tasks.py:900+` | Celery задача массового сопоставления |

### Алгоритм сопоставления

```
align_chapter() → 3 попытки LLM (порог: 98%→96%→95%) → fallback regex
```

**Ключевые методы**:
- `_check_volume_integrity()`: Проверка покрытия без `\n`
- `_parse_llm_response()`: Трёхуровневый парсинг JSON
- `_fallback_regex_alignment()`: Простое 1:1 по предложениям

### Формат данных

```json
{"alignments": [
  {"zh": "中文", "ru": "Русский", "type": "dialogue", "confidence": 0.95},
  {"zh": "...", "ru": "", "type": "author_note", "confidence": 1.0}
]}
```

**Типы**: dialogue, description, action, internal, author_note, translator_note

### API Endpoints

- `POST /api/bilingual/chapters/<id>/align` — Сопоставить главу
- `POST /api/bilingual/novels/<id>/align-chapters` — Массовое (Celery)
- `POST /api/novels/<id>/align-chapters/cancel` — Отмена

### Качество

- `quality_score = coverage_ru*0.3 + coverage_zh*0.3 + avg_confidence*0.4`
- Параллельные потоки: 2-5 (оптимально 3)
- Temperature: 0.1

---

## Chinese Learning Features

> **Полная документация**: [docs/CHINESE_LEARNING.md](docs/CHINESE_LEARNING.md)

**Функции изучения китайского через двуязычные EPUB**

### Компоненты

| Компонент | Путь | Назначение |
|-----------|------|------------|
| **ChineseRussianDictionary** | `utils/chinese_dictionary.py` | Словарь BKRS (StarDict) |
| **CharacterStatsTracker** | `utils/character_stats.py` | Статистика иероглифов |
| **PinyinHelper** | `utils/character_stats.py` | Работа с pinyin |

### Словарь BKRS

**Расположение**: `web_app/data/bkrs/` (не в git, ~300MB)

```bash
# Установка
mkdir -p web_app/data/bkrs
# Скачать с https://bkrs.info/ и распаковать
```

### Интеграция с EPUB

При генерации двуязычного EPUB добавляется блок статистики в конец каждой главы:
```
📊 Топ-20 иероглифов
他 (tā) — он, его [42×]
修 (xiū) — культивация [28×]
```
