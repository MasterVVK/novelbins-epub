#!/usr/bin/env python3
"""
Запуск веб-приложения из корня проекта
"""
import sys
import os
from dotenv import load_dotenv

# ВАЖНО: Загружаем .env файл ДО всего
load_dotenv()

# ВАЖНО: Устанавливаем переменные окружения ДО импорта app
os.environ.setdefault('CELERY_BROKER_URL', 'redis://localhost:6379/1')
os.environ.setdefault('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

# Добавляем папку web_app в путь для импорта
web_app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_app')
sys.path.insert(0, web_app_path)

# Переходим в папку web_app для корректной работы
# os.chdir(web_app_path)  # Закомментируем эту строку

from app import create_app, socketio, db

app = create_app()

@app.cli.command("init-db")
def init_db():
    """Инициализация базы данных"""
    db.create_all()
    print("База данных инициализирована!")

if __name__ == '__main__':
    # Безопасный запуск: debug только в development
    is_debug = os.environ.get('FLASK_ENV') == 'development' or os.environ.get('FLASK_DEBUG') == '1'
    host = '127.0.0.1' if not is_debug else '0.0.0.0'

    socketio.run(
        app,
        host=host,
        port=5001,
        debug=is_debug,
        allow_unsafe_werkzeug=is_debug
    ) 