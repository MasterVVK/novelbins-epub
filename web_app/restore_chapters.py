#!/usr/bin/env python3
"""
Скрипт для восстановления удаленных глав новеллы "Покрывая Небеса"
"""
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Novel, Chapter

def restore_deleted_chapters():
    """Восстановление удаленных глав"""
    app = create_app()
    with app.app_context():
        print("🔧 ВОССТАНОВЛЕНИЕ УДАЛЕННЫХ ГЛАВ")
        print("=" * 40)
        
        # Получаем новеллу
        novel = Novel.query.get(2)
        if not novel:
            print("❌ Новелла с ID=2 не найдена")
            return
        
        print(f"📖 Новелла: {novel.title}")
        
        # Получаем все удаленные главы
        deleted_chapters = Chapter.query.filter_by(
            novel_id=2,
            is_active=False
        ).order_by(Chapter.chapter_number).all()
        
        print(f"📚 Найдено удаленных глав: {len(deleted_chapters)}")
        
        if not deleted_chapters:
            print("✅ Нет удаленных глав для восстановления")
            return
        
        # Восстанавливаем каждую главу
        restored_count = 0
        for chapter in deleted_chapters:
            try:
                # Восстанавливаем главу
                chapter.is_active = True
                chapter.status = 'parsed'  # Устанавливаем статус как распарсенная
                
                print(f"✅ Восстановлена глава {chapter.chapter_number}: {chapter.original_title}")
                restored_count += 1
                
            except Exception as e:
                print(f"❌ Ошибка при восстановлении главы {chapter.chapter_number}: {e}")
        
        # Сохраняем изменения
        try:
            db.session.commit()
            print(f"\n📊 РЕЗУЛЬТАТ:")
            print(f"   Восстановлено глав: {restored_count}")
            
            # Обновляем статистику новеллы
            active_chapters = Chapter.query.filter_by(novel_id=2, is_active=True).count()
            novel.parsed_chapters = active_chapters
            novel.total_chapters = active_chapters
            db.session.commit()
            
            print(f"   Активных глав в новелле: {active_chapters}")
            print(f"   Статистика новеллы обновлена")
            
        except Exception as e:
            print(f"❌ Ошибка при сохранении: {e}")
            db.session.rollback()

def check_chapters_status():
    """Проверка статуса глав"""
    app = create_app()
    with app.app_context():
        print("\n🔍 ПРОВЕРКА СТАТУСА ГЛАВ")
        print("=" * 30)
        
        # Все главы
        all_chapters = Chapter.query.filter_by(novel_id=2).order_by(Chapter.chapter_number).all()
        print(f"📚 Всего глав: {len(all_chapters)}")
        
        # Активные главы
        active_chapters = Chapter.query.filter_by(novel_id=2, is_active=True).order_by(Chapter.chapter_number).all()
        print(f"✅ Активных глав: {len(active_chapters)}")
        
        # Удаленные главы
        deleted_chapters = Chapter.query.filter_by(novel_id=2, is_active=False).order_by(Chapter.chapter_number).all()
        print(f"🗑️ Удаленных глав: {len(deleted_chapters)}")
        
        # Показываем детали активных глав
        if active_chapters:
            print("\n📖 Активные главы:")
            for chapter in active_chapters:
                print(f"   Глава {chapter.chapter_number}: {chapter.original_title} ({chapter.status})")

if __name__ == '__main__':
    print("🚀 ЗАПУСК ВОССТАНОВЛЕНИЯ ГЛАВ")
    print("=" * 40)
    
    # Проверяем текущее состояние
    check_chapters_status()
    
    # Восстанавливаем главы
    restore_deleted_chapters()
    
    # Проверяем результат
    check_chapters_status()
    
    print("\n✅ ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО") 