#!/usr/bin/env python3
"""
Простой тест консольного вывода
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.log_service import LogService
from app.utils.console_buffer import add_console_message

app = create_app()

def test_console():
    with app.app_context():
        print("🧪 Простой тест консольного вывода")
        
        # Тест 1: Прямое добавление в консольный буфер
        add_console_message("🚀 Тест 1: Прямое сообщение", "INFO", "test")
        print("✅ Добавлено прямое сообщение")
        
        # Тест 2: Через LogService
        LogService.log_info("📝 Тест 2: Сообщение через LogService", novel_id=2)
        print("✅ Добавлено сообщение через LogService")
        
        # Тест 3: Сообщение редактора
        LogService.log_info("✏️ Начинаем редактуру главы 1", novel_id=2, chapter_id=7)
        print("✅ Добавлено сообщение редактора")
        
        # Тест 4: Сообщение переводчика
        LogService.log_info("🌐 Перевод главы 1 завершен", novel_id=2, chapter_id=7)
        print("✅ Добавлено сообщение переводчика")
        
        # Тест 5: Ошибка
        LogService.log_error("❌ Ошибка при обработке", novel_id=2)
        print("✅ Добавлено сообщение об ошибке")
        
        print("🌐 Откройте http://localhost:5001/console-test для просмотра")

if __name__ == "__main__":
    test_console() 