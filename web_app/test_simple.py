#!/usr/bin/env python3
"""
Простой тест системы логирования
"""
import sys
import os

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.services.log_service import LogService

app = create_app()

def test_simple():
    """Простой тест логирования"""
    with app.app_context():
        print("🧪 Простой тест системы логирования")
        print("=" * 40)
        
        # Создаем несколько логов
        LogService.log_info("Тестовое информационное сообщение")
        LogService.log_warning("Тестовое предупреждение")
        LogService.log_error("Тестовая ошибка")
        
        # Проверяем статистику
        stats = LogService.get_log_stats()
        print(f"📊 Статистика логов:")
        print(f"  - Всего: {stats['total']}")
        print(f"  - Ошибок: {stats['errors']}")
        print(f"  - Предупреждений: {stats['warnings']}")
        print(f"  - Информационных: {stats['info']}")
        
        # Получаем недавние логи
        recent_logs = LogService.get_recent_logs(hours=1, limit=5)
        print(f"\n📝 Последние логи:")
        for i, log in enumerate(recent_logs, 1):
            print(f"  {i}. [{log.level}] {log.message}")
        
        print("\n✅ Тест завершен успешно!")

if __name__ == '__main__':
    test_simple() 