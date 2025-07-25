#!/usr/bin/env python3
"""
Скрипт для тестирования консольного вывода
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.utils.console_buffer import add_console_message
import time

app = create_app()

def test_console():
    with app.app_context():
        print("🧪 Тестирование консольного вывода")
        
        # Добавляем тестовые сообщения
        add_console_message("🚀 Система запущена", "INFO", "system")
        time.sleep(1)
        
        add_console_message("📚 Начинаем парсинг новеллы 'Тестовая новелла'", "INFO", "parser")
        time.sleep(1)
        
        add_console_message("🔍 Поиск глав для новеллы...", "INFO", "parser")
        time.sleep(1)
        
        add_console_message("📖 Обработка главы 1/3: Введение", "INFO", "parser")
        time.sleep(1)
        
        add_console_message("⚠️ Глава 2 уже существует, пропускаем", "WARNING", "parser")
        time.sleep(1)
        
        add_console_message("📖 Обработка главы 3/3: Заключение", "INFO", "parser")
        time.sleep(1)
        
        add_console_message("✅ Парсинг завершен: 2/3 глав обработано", "INFO", "parser")
        time.sleep(1)
        
        add_console_message("🌐 Начинаем перевод главы 1", "INFO", "translator")
        time.sleep(1)
        
        add_console_message("❌ HTTP 503 для ключа #2", "ERROR", "translator")
        time.sleep(1)
        
        add_console_message("🔄 Переключение на ключ #3", "INFO", "translator")
        time.sleep(1)
        
        add_console_message("✅ Глава 1 переведена успешно", "INFO", "translator")
        time.sleep(1)
        
        add_console_message("✏️ Начинаем редактуру главы 1", "INFO", "editor")
        time.sleep(1)
        
        add_console_message("📊 Оценка качества главы 1: 8/10", "INFO", "editor")
        time.sleep(1)
        
        add_console_message("✅ Глава 1 отредактирована за 2.5 сек", "INFO", "editor")
        
        print("✅ Тестовые сообщения добавлены в консоль")
        print("🌐 Откройте http://localhost:5001/console-test для просмотра")

if __name__ == "__main__":
    test_console() 