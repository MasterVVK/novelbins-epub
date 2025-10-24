#!/usr/bin/env python3
"""
Тест отправки задачи в Celery из Flask app контекста
"""
import sys
import os

# ВАЖНО: Устанавливаем переменные окружения ДО импорта app
os.environ.setdefault('CELERY_BROKER_URL', 'redis://localhost:6379/1')
os.environ.setdefault('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, celery

app = create_app()

with app.app_context():
    print("=" * 50)
    print("Тест Celery конфигурации из Flask app")
    print("=" * 50)
    print(f"Celery broker: {celery.conf.broker_url}")
    print(f"Celery backend: {celery.conf.result_backend}")
    print(f"App config broker: {app.config['CELERY_BROKER_URL']}")
    print(f"App config backend: {app.config['CELERY_RESULT_BACKEND']}")
    print()

    # Пробуем отправить тестовую задачу
    from app.celery_tasks import cancel_parsing_task

    print("Отправляем тестовую задачу cancel_parsing_task...")
    task = cancel_parsing_task.apply_async(
        kwargs={'task_id': 'test-task-id'},
        queue='czbooks_queue'
    )

    print(f"✅ Task ID: {task.id}")
    print(f"✅ Task state: {task.state}")
    print()

    # Проверяем Redis
    import redis
    r = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)

    print("Ключи в Redis DB 1:")
    keys = r.keys('*')
    for key in keys[:10]:  # Первые 10 ключей
        print(f"  - {key}")

    if len(keys) > 10:
        print(f"  ... и еще {len(keys) - 10} ключей")

    print()
    print("Проверка завершена!")
