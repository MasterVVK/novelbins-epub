#!/usr/bin/env python3
"""
Отладочный скрипт для проверки парсера
"""
import traceback
from app import create_app, db
from app.models import Novel, Chapter, Task
from app.services.parser_service import WebParserService

def debug_parser():
    app = create_app()
    with app.app_context():
        print("🐛 ОТЛАДКА ПАРСЕРА")
        print("=" * 50)
        
        # Получаем новеллу
        novel = Novel.query.get(1)
        if not novel:
            print("❌ Новелла с ID=1 не найдена")
            return
        
        print(f"📖 Новелла: {novel.title}")
        print(f"🔗 URL: {novel.source_url}")
        
        # Создаем задачу
        task = Task(
            novel_id=1,
            task_type='parse',
            priority=1,
            status='running',
            progress=0
        )
        db.session.add(task)
        db.session.commit()
        print(f"✅ Задача создана: {task.id}")
        
        try:
            # Тестируем парсер
            print("\n🔧 Создание парсера...")
            parser = WebParserService()
            print("✅ Парсер создан")
            
            # Тестируем парсинг глав
            print("\n🔍 Парсинг списка глав...")
            chapters_data = parser.parse_novel_chapters(novel)
            
            if not chapters_data:
                print("❌ Не удалось получить список глав")
                return
            
            print(f"✅ Найдено глав: {len(chapters_data)}")
            
            # Тестируем парсинг первой главы
            if chapters_data:
                first_chapter = chapters_data[0]
                print(f"\n📖 Тестируем парсинг главы {first_chapter['number']}...")
                
                content = parser.parse_chapter_content(first_chapter['url'], first_chapter['number'])
                if content:
                    print(f"✅ Контент загружен: {len(content)} символов")
                    
                    # Создаем главу в БД
                    chapter = Chapter(
                        novel_id=1,
                        chapter_number=first_chapter['number'],
                        original_title=first_chapter['title'],
                        url=first_chapter['url'],
                        original_text=content,
                        status='parsed'
                    )
                    db.session.add(chapter)
                    db.session.commit()
                    print(f"✅ Глава сохранена в БД: {chapter.id}")
                else:
                    print("❌ Не удалось загрузить контент")
            
            # Обновляем задачу
            task.status = 'completed'
            task.progress = 100
            db.session.commit()
            print(f"✅ Задача завершена успешно")
            
        except Exception as e:
            print(f"❌ ОШИБКА: {e}")
            print("📋 Полный traceback:")
            traceback.print_exc()
            
            # Обновляем задачу
            task.status = 'failed'
            db.session.commit()

if __name__ == "__main__":
    debug_parser() 