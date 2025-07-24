# Novel Translator - Система перевода новелл

Веб-приложение для автоматического перевода новелл с использованием AI моделей.

## 🚀 Быстрый старт

### 1. Запуск приложения
```bash
# Способ 1: Через скрипт (рекомендуется)
./start_web.sh

# Способ 2: Вручную
source .venv/bin/activate && python run_web.py

# Способ 3: Из папки web_app
cd web_app && python run.py
```

### 2. Открыть в браузере
```
http://localhost:5001
```

## ⚙️ Настройки системы

### API Ключи
1. Откройте **Настройки** → **API ключи**
2. Добавьте ваши API ключи:
   - **Gemini API ключи** - ключи Google Gemini (по одному на строку)
   - **OpenAI API ключ** - ключ OpenAI (опционально)

### Параметры перевода
- **Модель по умолчанию**: Gemini 2.5 Flash / GPT-4o / Claude 3.5 Sonnet
- **Температура**: Креативность перевода (0-2)
- **Максимум токенов**: Лимит токенов для ответа
- **Задержка запросов**: Пауза между запросами (секунды)

### Параметры парсинга
- **Максимум глав**: Лимит глав для парсинга
- **Порог качества**: Минимальный балл качества (1-10)

## 📁 Структура проекта

```
novelbins-epub/
├── .venv/                    # Виртуальное окружение
├── web_app/                  # Веб-приложение
│   ├── app/                  # Flask приложение
│   │   ├── models/           # Модели данных
│   │   ├── services/         # Бизнес-логика
│   │   ├── templates/        # HTML шаблоны
│   │   └── views.py          # Контроллеры
│   ├── config/               # Конфигурация
│   ├── instance/             # База данных
│   └── run.py                # Запуск приложения
├── .env                      # Настройки с API ключами
├── requirements.txt          # Зависимости
├── run_web.py               # Запуск веб-приложения
├── start_web.sh             # Скрипт запуска
├── 1_parser_selenium.py      # Парсер глав
├── 2_translator_improved.py  # Переводчик
├── 3_editor.py              # Редактор
├── 4_epub_generator.py      # Генератор EPUB
├── database.py              # Работа с БД
├── models.py                # Модели данных
├── arch/                    # Архивные файлы
├── edited_translations/     # Отредактированные переводы
├── epub_output/             # Сгенерированные EPUB
├── parsed_chapters/         # Распарсенные главы
├── translations/            # Переводы
├── translations_problems/   # Проблемные переводы
├── translations.db          # Основная БД
└── README.md                # Документация
```

## 🔧 Система настроек

### Где хранятся настройки
Все настройки сохраняются в **базе данных SQLite** в таблице `system_settings`:

- **API ключи** - безопасно хранятся в БД
- **Параметры перевода** - модель, температура, токены
- **Настройки парсинга** - лимиты и пороги качества

### Просмотр настроек
```bash
cd web_app
python show_settings.py
```

### Программный доступ
```python
from app.services.settings_service import SettingsService

# Получить API ключи
keys = SettingsService.get_gemini_api_keys()
api_key = SettingsService.get_openai_api_key()

# Получить параметры
model = SettingsService.get_default_model()
temperature = SettingsService.get_default_temperature()
```

## 🗄️ База данных

### Основные таблицы
- **`novels`** - новеллы
- **`chapters`** - главы
- **`translations`** - переводы
- **`tasks`** - задачи
- **`system_settings`** - настройки системы

### Инициализация БД
```bash
cd web_app
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

## 🔑 API Ключи

### Поддерживаемые провайдеры
- **Google Gemini** - основной провайдер
- **OpenAI GPT** - альтернативный провайдер
- **Claude** - в разработке

### Ротация ключей
Система автоматически ротирует ключи Gemini для распределения нагрузки.

## 🚀 Разработка

### Установка зависимостей
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Запуск в режиме разработки
```bash
cd web_app
export FLASK_ENV=development
python run.py
```

### Логи
Логи приложения выводятся в консоль с подробной информацией о запросах к API.

## 📝 Лицензия

Проект для личного использования. 