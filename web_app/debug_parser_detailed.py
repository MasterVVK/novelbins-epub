#!/usr/bin/env python3
"""
Подробная диагностика парсинга для новеллы "Покрывая Небеса"
"""
import sys
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Novel, Chapter, Task
from app.services.parser_service import WebParserService

def test_parser_step_by_step():
    """Пошаговое тестирование парсера"""
    app = create_app()
    with app.app_context():
        print("🔍 ДИАГНОСТИКА ПАРСИНГА НОВЕЛЛЫ 'ПОКРЫВАЯ НЕБЕСА'")
        print("=" * 60)
        
        # Получаем новеллу
        novel = Novel.query.get(2)
        if not novel:
            print("❌ Новелла с ID=2 не найдена")
            return
        
        print(f"📖 Новелла: {novel.title}")
        print(f"🔗 URL: {novel.source_url}")
        print(f"⚙️ Конфигурация: {novel.config}")
        
        # Проверяем текущее состояние
        chapters_before = Chapter.query.filter_by(novel_id=2, is_active=True).count()
        print(f"📚 Глав в БД до парсинга: {chapters_before}")
        
        # Создаем парсер
        parser = WebParserService()
        
        try:
            print("\n🚀 НАЧИНАЕМ ПАРСИНГ...")
            
            # Тестируем парсинг глав
            print("\n1️⃣ Парсинг списка глав...")
            chapters_data = parser.parse_novel_chapters(novel)
            
            if not chapters_data:
                print("❌ Не удалось получить список глав")
                return
            
            print(f"✅ Найдено глав: {len(chapters_data)}")
            for i, chapter in enumerate(chapters_data[:3]):  # Показываем первые 3
                print(f"   Глава {chapter['number']}: {chapter['title']} - {chapter['url']}")
            
            # Тестируем парсинг содержимого первой главы
            if chapters_data:
                print(f"\n2️⃣ Парсинг содержимого главы {chapters_data[0]['number']}...")
                content = parser.parse_chapter_content(chapters_data[0]['url'], chapters_data[0]['number'])
                
                if content:
                    print(f"✅ Содержимое получено: {len(content)} символов")
                    print(f"📄 Начало текста: {content[:200]}...")
                    
                    # Пробуем сохранить в БД
                    print(f"\n3️⃣ Сохранение в базу данных...")
                    
                    # Проверяем, не существует ли уже глава
                    existing = Chapter.query.filter_by(
                        novel_id=2,
                        chapter_number=chapters_data[0]['number']
                    ).first()
                    
                    if existing:
                        print(f"⚠️ Глава {chapters_data[0]['number']} уже существует")
                    else:
                        # Создаем новую главу
                        chapter = Chapter(
                            novel_id=2,
                            chapter_number=chapters_data[0]['number'],
                            original_title=chapters_data[0]['title'],
                            url=chapters_data[0]['url'],
                            original_text=content,
                            status='parsed'
                        )
                        
                        try:
                            db.session.add(chapter)
                            db.session.commit()
                            print(f"✅ Глава {chapters_data[0]['number']} сохранена в БД")
                        except Exception as e:
                            print(f"❌ Ошибка при сохранении: {e}")
                            db.session.rollback()
                else:
                    print("❌ Не удалось получить содержимое главы")
            
            # Проверяем результат
            chapters_after = Chapter.query.filter_by(novel_id=2, is_active=True).count()
            print(f"\n📊 РЕЗУЛЬТАТ:")
            print(f"   Глав в БД после парсинга: {chapters_after}")
            print(f"   Добавлено глав: {chapters_after - chapters_before}")
            
        except Exception as e:
            print(f"❌ Ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            parser.cleanup_driver()

def check_database_state():
    """Проверка состояния базы данных"""
    app = create_app()
    with app.app_context():
        print("\n🔍 ПРОВЕРКА СОСТОЯНИЯ БАЗЫ ДАННЫХ")
        print("=" * 40)
        
        # Новелла
        novel = Novel.query.get(2)
        print(f"📖 Новелла: {novel.title}")
        print(f"   ID: {novel.id}")
        print(f"   Всего глав: {novel.total_chapters}")
        print(f"   Распарсено: {novel.parsed_chapters}")
        print(f"   Статус: {novel.status}")
        print(f"   Активна: {novel.is_active}")
        
        # Главы
        chapters = Chapter.query.filter_by(novel_id=2).all()
        print(f"\n📚 Главы в БД (все): {len(chapters)}")
        for chapter in chapters:
            print(f"   Глава {chapter.chapter_number}: {chapter.status} (активна: {chapter.is_active})")
        
        # Задачи
        tasks = Task.query.filter_by(novel_id=2, task_type='parse').order_by(Task.created_at.desc()).all()
        print(f"\n📋 Задачи парсинга: {len(tasks)}")
        for task in tasks:
            print(f"   Задача {task.id}: {task.status} - {task.progress}% (создана: {task.created_at})")

if __name__ == '__main__':
    print("🔧 ЗАПУСК ДИАГНОСТИКИ ПАРСИНГА")
    print("=" * 50)
    
    # Проверяем состояние БД до теста
    check_database_state()
    
    # Запускаем тест парсинга
    test_parser_step_by_step()
    
    # Проверяем состояние БД после теста
    check_database_state()
    
    print("\n✅ ДИАГНОСТИКА ЗАВЕРШЕНА") 