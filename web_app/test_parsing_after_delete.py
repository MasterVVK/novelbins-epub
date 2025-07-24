#!/usr/bin/env python3
"""
Тест поведения парсера после удаления глав
"""
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Novel, Chapter, Task
from app.services.parser_service import WebParserService

def test_parsing_after_delete():
    """Тестирование парсинга после удаления глав"""
    app = create_app()
    with app.app_context():
        print("🧪 ТЕСТ ПАРСИНГА ПОСЛЕ УДАЛЕНИЯ ГЛАВ")
        print("=" * 50)
        
        # Получаем новеллу
        novel = Novel.query.get(2)
        if not novel:
            print("❌ Новелла с ID=2 не найдена")
            return
        
        print(f"📖 Новелла: {novel.title}")
        
        # Проверяем текущее состояние
        active_chapters_before = Chapter.query.filter_by(novel_id=2, is_active=True).count()
        all_chapters_before = Chapter.query.filter_by(novel_id=2).count()
        print(f"📚 Активных глав до удаления: {active_chapters_before}")
        print(f"📚 Всего глав в БД: {all_chapters_before}")
        
        # Удаляем все активные главы (мягкое удаление)
        print("\n🗑️ УДАЛЕНИЕ ВСЕХ АКТИВНЫХ ГЛАВ...")
        active_chapters = Chapter.query.filter_by(novel_id=2, is_active=True).all()
        deleted_count = 0
        
        for chapter in active_chapters:
            chapter.soft_delete()
            print(f"   Удалена глава {chapter.chapter_number}: {chapter.original_title}")
            deleted_count += 1
        
        db.session.commit()
        print(f"✅ Удалено глав: {deleted_count}")
        
        # Проверяем состояние после удаления
        active_chapters_after_delete = Chapter.query.filter_by(novel_id=2, is_active=True).count()
        print(f"📚 Активных глав после удаления: {active_chapters_after_delete}")
        
        # Тестируем парсинг
        print("\n🚀 ТЕСТИРОВАНИЕ ПАРСИНГА...")
        
        # Создаем парсер
        parser = WebParserService()
        
        try:
            # Тестируем только парсинг списка глав (без сохранения)
            print("1️⃣ Парсинг списка глав...")
            chapters_data = parser.parse_novel_chapters(novel)
            
            if not chapters_data:
                print("❌ Не удалось получить список глав")
                return
            
            print(f"✅ Найдено глав на сайте: {len(chapters_data)}")
            
            # Проверяем, какие главы уже существуют в БД (включая удаленные)
            print("\n2️⃣ АНАЛИЗ СУЩЕСТВУЮЩИХ ГЛАВ В БД...")
            
            for chapter_data in chapters_data[:3]:  # Проверяем первые 3 главы
                chapter_number = chapter_data['number']
                
                # Ищем главу в БД (включая удаленные)
                existing_chapter = Chapter.query.filter_by(
                    novel_id=2,
                    chapter_number=chapter_number
                ).first()
                
                if existing_chapter:
                    print(f"   Глава {chapter_number}: найдена в БД (активна: {existing_chapter.is_active}, статус: {existing_chapter.status})")
                    
                    # Проверяем, что произойдет при парсинге
                    if existing_chapter.is_active:
                        print(f"     → Парсер ПРОПУСТИТ главу (уже существует и активна)")
                    else:
                        print(f"     → Парсер СОЗДАСТ НОВУЮ главу (существующая удалена)")
                else:
                    print(f"   Глава {chapter_number}: НЕ найдена в БД")
                    print(f"     → Парсер СОЗДАСТ НОВУЮ главу")
            
            # Тестируем создание новой главы
            print(f"\n3️⃣ ТЕСТ СОЗДАНИЯ НОВОЙ ГЛАВЫ...")
            
            if chapters_data:
                test_chapter = chapters_data[0]
                chapter_number = test_chapter['number']
                
                # Проверяем существование
                existing = Chapter.query.filter_by(
                    novel_id=2,
                    chapter_number=chapter_number
                ).first()
                
                if existing:
                    print(f"   Глава {chapter_number} существует в БД:")
                    print(f"     - ID: {existing.id}")
                    print(f"     - Активна: {existing.is_active}")
                    print(f"     - Статус: {existing.status}")
                    
                    if existing.is_active:
                        print(f"     → Парсер пропустит эту главу")
                    else:
                        print(f"     → Парсер создаст новую главу с тем же номером")
                        print(f"     → В БД будет ДВЕ записи для главы {chapter_number}")
                else:
                    print(f"   Глава {chapter_number} не найдена в БД")
                    print(f"     → Парсер создаст новую главу")
            
        except Exception as e:
            print(f"❌ Ошибка при тестировании: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            parser.cleanup_driver()

def simulate_parsing_behavior():
    """Симуляция поведения парсера"""
    app = create_app()
    with app.app_context():
        print("\n🔍 СИМУЛЯЦИЯ ПОВЕДЕНИЯ ПАРСЕРА")
        print("=" * 40)
        
        # Получаем новеллу
        novel = Novel.query.get(2)
        
        # Проверяем логику парсера
        print("📋 ЛОГИКА ПАРСЕРА:")
        print("   1. Парсер получает список глав с сайта")
        print("   2. Для каждой главы проверяет существование в БД:")
        print("      existing_chapter = Chapter.query.filter_by(")
        print("          novel_id=novel_id,")
        print("          chapter_number=chapter_data['number']")
        print("      ).first()")
        print("   3. Если глава существует (existing_chapter is not None):")
        print("      - Пропускает главу (continue)")
        print("      - НЕ проверяет is_active!")
        print("   4. Если главы НЕТ:")
        print("      - Парсит содержимое")
        print("      - Создает новую главу")
        
        print("\n⚠️ ПРОБЛЕМА:")
        print("   Парсер проверяет ТОЛЬКО существование главы по novel_id + chapter_number")
        print("   НЕ учитывает поле is_active!")
        print("   Если глава удалена (is_active=False), парсер все равно пропустит её")
        
        # Проверяем реальные данные
        print("\n📊 РЕАЛЬНЫЕ ДАННЫЕ:")
        chapters = Chapter.query.filter_by(novel_id=2).order_by(Chapter.chapter_number).all()
        
        for chapter in chapters[:5]:  # Показываем первые 5
            print(f"   Глава {chapter.chapter_number}: ID={chapter.id}, активна={chapter.is_active}, статус={chapter.status}")
        
        # Тестируем запрос парсера
        print(f"\n🧪 ТЕСТ ЗАПРОСА ПАРСЕРА:")
        for chapter_number in [1, 2, 3]:
            existing = Chapter.query.filter_by(
                novel_id=2,
                chapter_number=chapter_number
            ).first()
            
            if existing:
                print(f"   Глава {chapter_number}: найдена (ID={existing.id}, активна={existing.is_active})")
                print(f"     → Парсер ПРОПУСТИТ главу")
            else:
                print(f"   Глава {chapter_number}: НЕ найдена")
                print(f"     → Парсер СОЗДАСТ главу")

if __name__ == '__main__':
    print("🔧 ЗАПУСК ТЕСТА ПАРСИНГА ПОСЛЕ УДАЛЕНИЯ")
    print("=" * 50)
    
    # Симуляция поведения
    simulate_parsing_behavior()
    
    # Тестирование
    test_parsing_after_delete()
    
    print("\n✅ ТЕСТ ЗАВЕРШЕН") 