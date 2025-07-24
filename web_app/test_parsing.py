#!/usr/bin/env python3
"""
Скрипт для тестирования парсинга с подробной диагностикой
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Novel, Chapter, Task
from app.services.parser_service import WebParserService
import time

def test_parsing():
    """Тестирование парсинга с подробной диагностикой"""
    app = create_app()
    
    with app.app_context():
        try:
            # Получаем первую активную новеллу
            novel = Novel.query.filter_by(is_active=True).first()
            if not novel:
                print("❌ Нет активных новелл в базе данных")
                return
            
            print(f"🔍 Тестирование парсинга для новеллы: {novel.title}")
            print(f"📖 URL: {novel.source_url}")
            print(f"⚙️ Конфигурация: {novel.config}")
            
            # Проверяем настройки
            if novel.config:
                max_chapters = novel.config.get('max_chapters', 10)
                request_delay = novel.config.get('request_delay', 1.0)
                print(f"📊 Максимум глав: {max_chapters}")
                print(f"⏱️ Задержка запросов: {request_delay}")
            else:
                print("⚠️ Конфигурация новеллы не найдена")
            
            # Создаем задачу для отслеживания
            task = Task(
                novel_id=novel.id,
                task_type='parse',
                status='running',
                progress=0
            )
            db.session.add(task)
            db.session.commit()
            print(f"✅ Задача создана: {task.id}")
            
            # Запускаем парсинг
            print("\n🚀 Запуск парсинга...")
            start_time = time.time()
            
            parser = WebParserService()
            success = parser.parse_novel(novel.id)
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"\n⏱️ Время выполнения: {duration:.2f} секунд")
            print(f"✅ Результат: {'успешно' if success else 'с ошибкой'}")
            
            # Проверяем результат
            chapters_count = Chapter.query.filter_by(novel_id=novel.id, is_active=True).count()
            print(f"📊 Создано глав: {chapters_count}")
            
            # Обновляем статус задачи
            task.status = 'completed' if success else 'failed'
            task.progress = 100 if success else 0
            db.session.commit()
            
            if success:
                print("🎉 Парсинг завершен успешно!")
            else:
                print("❌ Парсинг завершился с ошибкой")
                
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    print("🧪 Тестирование парсинга...")
    test_parsing()
    print("✅ Тестирование завершено") 