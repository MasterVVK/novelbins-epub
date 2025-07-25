#!/usr/bin/env python3
"""
Тест консольного вывода при редактуре
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import Chapter, Novel
from app.services.translator_service import TranslatorService
from app.services.editor_service import EditorService
from app.utils.console_buffer import add_console_message

app = create_app()

def test_editor_console():
    with app.app_context():
        print("🧪 Тестирование консольного вывода при редактуре")
        
        # Добавляем тестовое сообщение в консоль
        add_console_message("🚀 Тест редактуры начат", "INFO", "test")
        
        # Находим первую главу для тестирования
        chapter = Chapter.query.filter_by(is_active=True).first()
        
        if not chapter:
            print("❌ Нет глав для тестирования")
            return
            
        print(f"📖 Тестируем редактуру главы {chapter.chapter_number}")
        
        # Создаем сервисы
        translator_service = TranslatorService()
        editor_service = EditorService(translator_service)
        
        # Запускаем редактуру
        try:
            success = editor_service.edit_chapter(chapter)
            if success:
                add_console_message("✅ Тест редактуры завершен успешно", "INFO", "test")
                print("✅ Тест редактуры завершен успешно")
            else:
                add_console_message("❌ Тест редактуры завершен с ошибкой", "ERROR", "test")
                print("❌ Тест редактуры завершен с ошибкой")
        except Exception as e:
            add_console_message(f"❌ Ошибка теста редактуры: {e}", "ERROR", "test")
            print(f"❌ Ошибка теста редактуры: {e}")
        
        print("🌐 Откройте http://localhost:5001/console-test для просмотра логов")

if __name__ == "__main__":
    test_editor_console() 