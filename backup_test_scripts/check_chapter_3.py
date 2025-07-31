#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter, Translation

app = create_app()

with app.app_context():
    print("🔍 Детальная проверка главы 3...")
    
    # Получаем главу 3
    chapter = Chapter.query.filter_by(
        novel_id=2,
        chapter_number=3,
        is_active=True
    ).first()
    
    if not chapter:
        print("❌ Глава 3 не найдена")
        exit(1)
    
    print(f"📖 Глава: {chapter.original_title}")
    print(f"📊 Статус: {chapter.status}")
    print(f"📝 Оригинальный текст: {'Есть' if chapter.original_text else 'Нет'}")
    
    # Проверяем переводы
    print(f"\n📋 Всего переводов: {len(chapter.translations)}")
    for i, trans in enumerate(chapter.translations):
        print(f"  Перевод {i+1}: {trans.translation_type} ({trans.api_used})")
        print(f"    Длина: {len(trans.translated_text)} символов")
        print(f"    Создан: {trans.created_at}")
    
    # Проверяем свойства
    print(f"\n🔍 Свойства главы:")
    print(f"  current_translation: {'Есть' if chapter.current_translation else 'Нет'}")
    print(f"  edited_translation: {'Есть' if chapter.edited_translation else 'Нет'}")
    print(f"  is_translated: {chapter.is_translated}")
    print(f"  is_edited: {chapter.is_edited}")
    
    # Проверяем, готова ли глава для редактуры
    if chapter.status == 'translated' and chapter.current_translation:
        print(f"\n✅ Глава готова для редактуры!")
        print(f"  Статус: {chapter.status}")
        print(f"  Есть перевод: {len(chapter.current_translation.translated_text)} символов")
    else:
        print(f"\n❌ Глава НЕ готова для редактуры")
        print(f"  Статус: {chapter.status}")
        print(f"  Перевод: {'Есть' if chapter.current_translation else 'Нет'}")
    
    # Проверяем задачи редактуры
    from app.models import Task
    editing_tasks = Task.query.filter_by(
        novel_id=2,
        task_type='editing'
    ).order_by(Task.created_at.desc()).all()
    
    print(f"\n📋 Задачи редактуры: {len(editing_tasks)}")
    for task in editing_tasks:
        print(f"  Задача {task.id}: {task.status} (создана: {task.created_at})")
        if hasattr(task, 'error_message') and task.error_message:
            print(f"    Ошибка: {task.error_message}")
        if hasattr(task, 'result') and task.result:
            print(f"    Результат: {task.result}") 