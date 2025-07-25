#!/usr/bin/env python3
"""
Запуск веб-приложения из корня проекта
"""
import sys
import os

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
    socketio.run(app, host='0.0.0.0', port=5001, debug=True, allow_unsafe_werkzeug=True) 