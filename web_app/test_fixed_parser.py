#!/usr/bin/env python3
"""
Тест исправленной логики парсера
"""
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Novel, Chapter, Task
from app.services.parser_service import WebParserService

def test_fixed_parser_logic():
    """Тестирование исправленной логики парсера"""
    app = create_app()
    with app.app_context():
        print("🔧 ТЕСТ ИСПРАВЛЕННОЙ ЛОГИКИ ПАРСЕРА")
        print("=" * 50)
        
        # Получаем новеллу
        novel = Novel.query.get(2)
        if not novel:
            print("❌ Новелла с ID=2 не найдена")
            return
        
        print(f"📖 Новелла: {novel.title}")
        
        # Проверяем текущее состояние
        active_chapters = Chapter.query.filter_by(novel_id=2, is_active=True).count()
        deleted_chapters = Chapter.query.filter_by(novel_id=2, is_active=False).count()
        print(f"📚 Активных глав: {active_chapters}")
        print(f"🗑️ Удаленных глав: {deleted_chapters}")
        
        # Тестируем исправленную логику парсера
        print("\n🧪 ТЕСТИРОВАНИЕ ИСПРАВЛЕННОЙ ЛОГИКИ...")
        
        # Создаем парсер
        parser = WebParserService()
        
        try:
            # Тестируем парсинг списка глав
            print("1️⃣ Парсинг списка глав...")
            chapters_data = parser.parse_novel_chapters(novel)
            
            if not chapters_data:
                print("❌ Не удалось получить список глав")
                return
            
            print(f"✅ Найдено глав на сайте: {len(chapters_data)}")
            
            # Тестируем логику проверки существования
            print("\n2️⃣ ТЕСТ ЛОГИКИ ПРОВЕРКИ СУЩЕСТВОВАНИЯ...")
            
            for chapter_data in chapters_data[:3]:  # Проверяем первые 3 главы
                chapter_number = chapter_data['number']
                
                # Используем исправленную логику парсера
                existing_chapter = Chapter.query.filter_by(
                    novel_id=2,
                    chapter_number=chapter_number,
                    is_active=True
                ).first()
                
                if existing_chapter:
                    print(f"   Глава {chapter_number}: найдена активная глава (ID={existing_chapter.id})")
                    print(f"     → Парсер ПРОПУСТИТ главу")
                else:
                    print(f"   Глава {chapter_number}: активная глава НЕ найдена")
                    
                    # Проверяем, есть ли удаленная глава
                    deleted_chapter = Chapter.query.filter_by(
                        novel_id=2,
                        chapter_number=chapter_number,
                        is_active=False
                    ).first()
                    
                    if deleted_chapter:
                        print(f"     → Найдена удаленная глава (ID={deleted_chapter.id})")
                        print(f"     → Парсер СОЗДАСТ НОВУЮ главу")
                    else:
                        print(f"     → Глава полностью отсутствует в БД")
                        print(f"     → Парсер СОЗДАСТ НОВУЮ главу")
            
            # Тестируем создание новой главы
            print(f"\n3️⃣ ТЕСТ СОЗДАНИЯ НОВОЙ ГЛАВЫ...")
            
            if chapters_data:
                test_chapter = chapters_data[0]
                chapter_number = test_chapter['number']
                
                # Проверяем, сколько глав с таким номером уже есть
                all_chapters_with_number = Chapter.query.filter_by(
                    novel_id=2,
                    chapter_number=chapter_number
                ).all()
                
                active_chapters_with_number = Chapter.query.filter_by(
                    novel_id=2,
                    chapter_number=chapter_number,
                    is_active=True
                ).all()
                
                print(f"   Глава {chapter_number}:")
                print(f"     - Всего записей в БД: {len(all_chapters_with_number)}")
                print(f"     - Активных записей: {len(active_chapters_with_number)}")
                
                if active_chapters_with_number:
                    print(f"     → Парсер пропустит главу (есть активная)")
                else:
                    print(f"     → Парсер создаст новую главу")
                    print(f"     → После парсинга будет {len(all_chapters_with_number) + 1} записей")
            
        except Exception as e:
            print(f"❌ Ошибка при тестировании: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            parser.cleanup_driver()

def test_actual_parsing():
    """Тестирование реального парсинга"""
    app = create_app()
    with app.app_context():
        print("\n🚀 ТЕСТ РЕАЛЬНОГО ПАРСИНГА")
        print("=" * 40)
        
        # Получаем новеллу
        novel = Novel.query.get(2)
        
        # Создаем парсер
        parser = WebParserService()
        
        try:
            print("🔧 Запуск реального парсинга...")
            
            # Запускаем парсинг
            success = parser.parse_novel(2)
            
            if success:
                print("✅ Парсинг завершен успешно")
                
                # Проверяем результат
                active_chapters_after = Chapter.query.filter_by(novel_id=2, is_active=True).count()
                all_chapters_after = Chapter.query.filter_by(novel_id=2).count()
                
                print(f"📊 РЕЗУЛЬТАТ:")
                print(f"   Активных глав: {active_chapters_after}")
                print(f"   Всего глав в БД: {all_chapters_after}")
                
                # Показываем детали
                active_chapters = Chapter.query.filter_by(novel_id=2, is_active=True).order_by(Chapter.chapter_number).all()
                print(f"\n📖 Активные главы:")
                for chapter in active_chapters:
                    print(f"   Глава {chapter.chapter_number}: {chapter.original_title} (ID={chapter.id})")
                
            else:
                print("❌ Парсинг завершился с ошибкой")
                
        except Exception as e:
            print(f"❌ Ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            parser.cleanup_driver()

if __name__ == '__main__':
    print("🔧 ЗАПУСК ТЕСТА ИСПРАВЛЕННОГО ПАРСЕРА")
    print("=" * 50)
    
    # Тестируем логику
    test_fixed_parser_logic()
    
    # Тестируем реальный парсинг
    test_actual_parsing()
    
    print("\n✅ ТЕСТ ЗАВЕРШЕН") 