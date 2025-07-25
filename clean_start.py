#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter, GlossaryItem, Task

app = create_app()

with app.app_context():
    print("🧹 Начинаем полную очистку системы...")
    
    # 1. Удаляем все задачи
    tasks_deleted = Task.query.delete()
    print(f"✅ Удалено задач: {tasks_deleted}")
    
    # 2. Удаляем все элементы глоссария
    glossary_deleted = GlossaryItem.query.delete()
    print(f"✅ Удалено элементов глоссария: {glossary_deleted}")
    
    # 3. Удаляем все главы
    chapters_deleted = Chapter.query.delete()
    print(f"✅ Удалено глав: {chapters_deleted}")
    
    # 4. Сбрасываем счетчики новеллы
    novel = Novel.query.get(2)  # "Покрывая Небеса"
    if novel:
        novel.parsed_chapters = 0
        novel.translated_chapters = 0
        novel.edited_chapters = 0
        novel.status = 'pending'
        db.session.add(novel)
        print(f"✅ Сброшены счетчики новеллы: {novel.title}")
    
    # 5. Сохраняем изменения
    db.session.commit()
    
    print("\n🎯 Система полностью очищена!")
    print("📊 Текущее состояние:")
    print(f"  - Новелл: {Novel.query.count()}")
    print(f"  - Глав: {Chapter.query.count()}")
    print(f"  - Элементов глоссария: {GlossaryItem.query.count()}")
    print(f"  - Задач: {Task.query.count()}")
    
    if novel:
        print(f"\n📚 Новелла '{novel.title}':")
        print(f"  - Статус: {novel.status}")
        print(f"  - Распарсено глав: {novel.parsed_chapters}")
        print(f"  - Переведено глав: {novel.translated_chapters}")
        print(f"  - Отредактировано глав: {novel.edited_chapters}")
    
    print("\n🚀 Готово к новому запуску!") 