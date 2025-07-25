#!/usr/bin/env python3
"""
Тестирование системы логирования
"""
import sys
import os
import time

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.services.log_service import LogService
from app.models import Task, Novel

app = create_app()

def test_logging():
    """Тестирование системы логирования"""
    with app.app_context():
        print("🧪 Тестирование системы логирования")
        print("=" * 50)
        
        # Создаем тестовую задачу
        print("📝 Создаем тестовую задачу...")
        task = Task(
            novel_id=1,
            task_type='test',
            status='running',
            progress=0
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id
        print(f"✅ Задача создана с ID: {task_id}")
        
        # Тестируем логирование
        print("\n📊 Тестируем различные типы логов...")
        
        # Информационные логи
        LogService.log_info("Тестовое информационное сообщение", task_id=task_id)
        LogService.log_info("Начинаем обработку данных", task_id=task_id, 
                           extra_data={'step': 'initialization', 'data_count': 100})
        
        # Предупреждения
        LogService.log_warning("Обнаружено потенциальная проблема", task_id=task_id)
        LogService.log_warning("Медленное соединение с API", task_id=task_id,
                              extra_data={'api_url': 'https://api.example.com', 'response_time': 5.2})
        
        # Ошибки
        LogService.log_error("Критическая ошибка при обработке", task_id=task_id)
        LogService.log_error("Не удалось подключиться к базе данных", task_id=task_id,
                            extra_data={'error_code': 500, 'retry_count': 3})
        
        # Отладочная информация
        LogService.log_debug("Отладочная информация", task_id=task_id)
        
        # Проверяем сохранение логов
        print("\n🔍 Проверяем сохранение логов...")
        logs = LogService.get_task_logs(task_id)
        print(f"✅ Найдено логов для задачи {task_id}: {len(logs)}")
        
        for i, log in enumerate(logs[:5]):  # Показываем первые 5 логов
            print(f"  {i+1}. [{log.level}] {log.message}")
        
        # Тестируем статистику
        print("\n📈 Тестируем статистику логов...")
        stats = LogService.get_log_stats()
        print(f"✅ Общая статистика:")
        print(f"  - Всего логов: {stats['total']}")
        print(f"  - Ошибок: {stats['errors']}")
        print(f"  - Предупреждений: {stats['warnings']}")
        print(f"  - Информационных: {stats['info']}")
        print(f"  - За 24 часа: {stats['recent_24h']}")
        
        # Тестируем фильтрацию
        print("\n🔍 Тестируем фильтрацию логов...")
        error_logs = LogService.get_error_logs(limit=10)
        print(f"✅ Найдено ошибок: {len(error_logs)}")
        
        recent_logs = LogService.get_recent_logs(hours=1, limit=10)
        print(f"✅ Логов за последний час: {len(recent_logs)}")
        
        # Очищаем тестовую задачу
        print("\n🧹 Очищаем тестовые данные...")
        db.session.delete(task)
        db.session.commit()
        print("✅ Тестовая задача удалена")
        
        print("\n🎉 Тестирование завершено успешно!")

if __name__ == '__main__':
    test_logging() 