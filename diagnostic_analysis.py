#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter, Translation, Task

app = create_app()

def analyze_editing_problem():
    """Комплексный анализ проблемы с редактурой"""
    print("🔍 КОМПЛЕКСНЫЙ АНАЛИЗ ПРОБЛЕМЫ РЕДАКТУРЫ")
    print("=" * 60)
    
    with app.app_context():
        # 1. Анализ новеллы
        print("\n📚 1. АНАЛИЗ НОВЕЛЛЫ")
        novel = Novel.query.get(2)
        if not novel:
            print("❌ Новелла не найдена!")
            return
        
        print(f"📖 Название: {novel.title}")
        print(f"📊 Статус: {novel.status}")
        print(f"📈 Глав всего: {novel.total_chapters}")
        print(f"📈 Глав распарсено: {novel.parsed_chapters}")
        print(f"📈 Глав переведено: {novel.translated_chapters}")
        print(f"📈 Глав отредактировано: {novel.edited_chapters}")
        
        # 2. Анализ глав
        print("\n📋 2. АНАЛИЗ ГЛАВ")
        chapters = Chapter.query.filter_by(novel_id=2, is_active=True).order_by(Chapter.chapter_number).all()
        
        for chapter in chapters:
            print(f"\n  Глава {chapter.chapter_number}: {chapter.original_title}")
            print(f"    Статус: {chapter.status}")
            print(f"    Переводов: {len(chapter.translations)}")
            
            if chapter.translations:
                for i, trans in enumerate(chapter.translations):
                    print(f"      Перевод {i+1}: {trans.translation_type} ({trans.api_used}) - {len(trans.translated_text)} символов")
            
            # Проверяем готовность к редактуре
            if chapter.status == 'translated' and chapter.current_translation:
                print(f"    ✅ ГОТОВА К РЕДАКТУРЕ")
            elif chapter.status == 'edited':
                print(f"    ✅ УЖЕ ОТРЕДАКТИРОВАНА")
            else:
                print(f"    ❌ НЕ ГОТОВА К РЕДАКТУРЕ")
        
        # 3. Анализ задач редактуры
        print("\n🎯 3. АНАЛИЗ ЗАДАЧ РЕДАКТУРЫ")
        editing_tasks = Task.query.filter_by(novel_id=2, task_type='editing').order_by(Task.created_at.desc()).all()
        
        if not editing_tasks:
            print("  ❌ Задач редактуры не найдено")
        else:
            for task in editing_tasks:
                print(f"\n  Задача {task.id}:")
                print(f"    Статус: {task.status}")
                print(f"    Прогресс: {task.progress}")
                print(f"    Создана: {task.created_at}")
                print(f"    Начата: {task.started_at}")
                print(f"    Завершена: {task.completed_at}")
                if task.error_message:
                    print(f"    ❌ Ошибка: {task.error_message}")
                if task.result:
                    print(f"    📄 Результат: {task.result}")
        
        # 4. Поиск глав готовых к редактуре
        print("\n🎯 4. ГЛАВЫ ГОТОВЫЕ К РЕДАКТУРЕ")
        ready_chapters = Chapter.query.filter_by(
            novel_id=2,
            status='translated',
            is_active=True
        ).order_by(Chapter.chapter_number).all()
        
        if not ready_chapters:
            print("  ❌ Нет глав готовых к редактуре")
        else:
            print(f"  ✅ Найдено {len(ready_chapters)} глав готовых к редактуре:")
            for chapter in ready_chapters:
                print(f"    - Глава {chapter.chapter_number}: {chapter.original_title}")
        
        # 5. Проверка конфигурации
        print("\n⚙️ 5. КОНФИГУРАЦИЯ")
        if novel.config:
            print(f"  Макс. глав: {novel.config.get('max_chapters')}")
            print(f"  Задержка: {novel.config.get('request_delay')}")
            print(f"  Модель: {novel.config.get('translation_model')}")
            print(f"  Температура: {novel.config.get('temperature')}")
        else:
            print("  ❌ Конфигурация не найдена")
        
        # 6. Рекомендации
        print("\n💡 6. РЕКОМЕНДАЦИИ")
        if ready_chapters:
            print("  ✅ Есть главы для редактуры - можно запускать")
            print("  🔧 Возможные проблемы:")
            print("    - Задача зависла в статусе 'pending'")
            print("    - Проблема с фоновым потоком")
            print("    - Ошибка в EditorService")
        else:
            print("  ❌ Нет глав для редактуры")
            print("  🔧 Решения:")
            print("    - Запустить перевод для глав со статусом 'parsed'")
            print("    - Проверить статусы глав")

if __name__ == "__main__":
    analyze_editing_problem() 