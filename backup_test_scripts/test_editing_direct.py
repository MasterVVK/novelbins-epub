#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter, Task
from app.services.translator_service import TranslatorService
from app.services.editor_service import EditorService
import time

app = create_app()

with app.app_context():
    print("🧪 Тестируем функцию редактуры напрямую...")
    
    # Получаем новеллу
    novel = Novel.query.get(2)
    if not novel:
        print("❌ Новелла с ID 2 не найдена")
        exit(1)
    
    print(f"📖 Найдена новелла: {novel.title}")
    
    # Получаем главы для редактуры
    chapters = Chapter.query.filter_by(
        novel_id=2,
        status='translated',
        is_active=True
    ).order_by(Chapter.chapter_number).all()
    
    print(f"🔍 Найдено глав для редактуры: {len(chapters)}")
    for ch in chapters:
        print(f"  - Глава {ch.chapter_number}: {ch.original_title} (статус: {ch.status})")
    
    if not chapters:
        print("❌ Нет глав для редактуры")
        exit(1)
    
    # Создаем задачу редактуры
    task = Task(
        novel_id=2,
        task_type='editing',
        priority=2
    )
    db.session.add(task)
    db.session.commit()
    print(f"✅ Создана задача редактуры с ID: {task.id}")
    
    # Инициализируем сервисы
    translator_service = TranslatorService()
    editor_service = EditorService(translator_service)
    
    total_chapters = len(chapters)
    success_count = 0
    
    print(f"🚀 Начинаем редактуру {total_chapters} глав")
    
    for i, chapter in enumerate(chapters, 1):
        try:
            print(f"📝 Редактируем главу {chapter.chapter_number} ({i}/{total_chapters})")
            
            # Обновляем прогресс
            progress = (i / total_chapters) * 100
            task.update_progress(progress / 100, f"Редактура главы {chapter.chapter_number}")
            
            # Редактируем главу
            success = editor_service.edit_chapter(chapter)
            if success:
                success_count += 1
                print(f"✅ Глава {chapter.chapter_number} отредактирована")
            else:
                print(f"❌ Ошибка редактуры главы {chapter.chapter_number}")
            
            time.sleep(2)  # Пауза между главами
            
        except Exception as e:
            print(f"❌ Ошибка редактуры главы {i}: {e}")
            continue
    
    # Обновляем счетчик отредактированных глав
    if success_count > 0:
        novel.edited_chapters = success_count
        db.session.add(novel)
        db.session.commit()
        print(f"📊 Обновлен счетчик отредактированных глав: {success_count}")
    
    # Завершаем задачу
    if success_count == total_chapters:
        task.complete(f"Редактура завершена: {success_count}/{total_chapters} глав")
    else:
        task.complete(f"Редактура завершена с ошибками: {success_count}/{total_chapters} глав")
    
    print(f"✅ Редактура завершена: {success_count}/{total_chapters} глав") 