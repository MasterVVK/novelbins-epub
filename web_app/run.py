#!/usr/bin/env python3
"""
Запуск Flask приложения
"""
import sys
import os

# ВАЖНО: Устанавливаем переменные окружения ДО импорта app
os.environ.setdefault('CELERY_BROKER_URL', 'redis://localhost:6379/1')
os.environ.setdefault('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, socketio, db

app = create_app()

@app.cli.command("init-db")
def init_db():
    """Инициализация базы данных"""
    db.create_all()
    print("База данных инициализирована!")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True, allow_unsafe_werkzeug=True)
