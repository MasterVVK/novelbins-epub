# Repository Guidelines

## Структура проекта
- Основное приложение Flask: `web_app/app` (views, `api/`, `services/`, `models/`, `templates/`, `static/`).
- Парсеры источников: `parsers/` (`sources/`, `base/`, `parser_factory.py`), завязаны на Selenium/undetected-chromedriver.
- Скрипты запуска и обслуживания: корневые `run_web.py`, `start_web.sh`, `run-kimi.sh`, celery-скрипты в `web_app/`.
- Тесты и отладочные проверки: корневые `test_*.py`, `web_app/test_bilingual_system.py`; ожидают рабочую БД и данные.
- Логи и артефакты: `logs/`, `uploads/`; не коммить результаты работы.

## Сборка, запуск и разработка
- Подготовка окружения: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
- Инициализация БД: `python run_web.py init-db` или `cd web_app && flask db upgrade`.
- Запуск веб-сервера: `python run_web.py` (порт 5001, читает `.env`).
- Celery worker: `cd web_app && ./start_celery_worker.sh` (требуется запущенный Redis).
- Быстрый полный стек для локальной отладки: параллельно веб-сервер + worker; для VNC/Cloudflare solver нужны Chrome/Chromium и Ollama (см. README).

## Стиль кода и соглашения
- Python 3.10+, PEP8, 4 пробела; именование `snake_case` для функций/переменных, `PascalCase` для классов, модули в нижнем регистре.
- Используйте type hints и короткие docstring на русском по аналогии с существующими сервисами (`UniversalLLMTranslator`, `parser_service`).
- Логирование через стандартный `logging` и `LogService`, не оставляйте отладочные принты в прод-коде.
- Конфигурация через `.env` и `web_app/config`; не хардкодьте ключи API.

## Тестирование
- Базовый прогон: `pytest -q` из корня; точечно `pytest test_logs_filters.py` или `pytest web_app/test_bilingual_system.py`.
- Многие тесты интеграционные: им нужен созданный `instance/novel_translator.db`, заполненные новеллы/главы и доступ к Redis/AI моделям — документируйте требования в описании PR.
- Новые функции покрывайте минимальными unit-тестами без внешних сервисов; для тяжелых задач — фикстуры с моками моделей/сервисов.

## Коммиты и Pull Requests
- Коммиты краткие и в повелительном наклонении (`add alignment retries`, `fix celery logging`); избегайте шумных правок форматирования.
- Для PR: чёткое описание задачи, ссылка на issue/обсуждение, шаги для воспроизведения/проверки, скриншоты UI или ключевые логи при изменениях в пайплайнах.
- Не включайте в дифф временные файлы, логи, артефакты EPUB, `.env`, данные словаря BKRS.

## Безопасность и конфигурация
- Храните API-ключи Gemini/OpenAI/Anthropic и настройки прокси только в `.env`; не выкладывайте их в репозиторий или логи.
- Для задач с Cloudflare/Ollama проверяйте наличие модели (`ollama list`) и следите за ограничениями GPU/памяти.
- Перед пушем убедитесь, что `logs/` и `uploads/` чисты, а миграции БД (`web_app/migrations/`) актуальны при изменениях моделей.
