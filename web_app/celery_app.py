"""
Celery application для запуска worker
"""
import os
from dotenv import load_dotenv

# ВАЖНО: Загружаем .env файл ДО импорта app
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from app import create_app, celery

# Создаём Flask app для контекста
flask_app = create_app()

# Импортируем задачи чтобы Celery их зарегистрировал
from app import celery_tasks

# Celery уже настроен в create_app()
# Теперь worker увидит все задачи из celery_tasks
