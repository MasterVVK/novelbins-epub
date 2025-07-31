#!/usr/bin/env python3
"""
Скрипт для отладки статусов глав в реальных данных.
"""

import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import create_app, db
from app.models import Novel, Chapter
from app.utils.status_colors import status_colors


def debug_chapter_statuses():
    """Отладка статусов глав"""
    
    print("🔍 Отладка статусов глав в реальных данных\n")
    
    app = create_app('development')
    
    with app.app_context():
        # Получаем все новеллы
        novels = Novel.query.all()
        
        for novel in novels:
            print(f"📚 Новелла: {novel.title} (ID: {novel.id})")
            print(f"   Статус новеллы: {novel.status}")
            
            # Получаем главы
            chapters = Chapter.query.filter_by(novel_id=novel.id).order_by(Chapter.chapter_number).all()
            
            if chapters:
                print("   Главы:")
                for chapter in chapters:
                    # Получаем цвет для статуса главы
                    color = status_colors.get_chapter_status_color(chapter.status)
                    icon = status_colors.get_status_icon(chapter.status, 'chapter')
                    text = status_colors.get_status_text(chapter.status, 'chapter')
                    
                    print(f"     Глава {chapter.chapter_number}: {chapter.status} → {color} | {icon} | {text}")
                    
                    # Проверяем, что статус соответствует ожидаемому
                    if chapter.status == 'translated':
                        expected_color = 'primary'
                        if color != expected_color:
                            print(f"       ⚠️  ОШИБКА: ожидался {expected_color}, получен {color}")
                    elif chapter.status == 'edited':
                        expected_color = 'success'
                        if color != expected_color:
                            print(f"       ⚠️  ОШИБКА: ожидался {expected_color}, получен {color}")
                    elif chapter.status == 'parsed':
                        expected_color = 'info'
                        if color != expected_color:
                            print(f"       ⚠️  ОШИБКА: ожидался {expected_color}, получен {color}")
                    elif chapter.status == 'error':
                        expected_color = 'danger'
                        if color != expected_color:
                            print(f"       ⚠️  ОШИБКА: ожидался {expected_color}, получен {color}")
                    elif chapter.status == 'pending':
                        expected_color = 'secondary'
                        if color != expected_color:
                            print(f"       ⚠️  ОШИБКА: ожидался {expected_color}, получен {color}")
            else:
                print("   Главы не найдены")
            
            print()


def test_filter_rendering():
    """Тест рендеринга фильтров для реальных данных"""
    
    print("🎨 Тест рендеринга фильтров\n")
    
    app = create_app('development')
    
    with app.app_context():
        # Получаем первую новеллу с главами
        novel = Novel.query.first()
        if not novel:
            print("Новеллы не найдены")
            return
        
        chapters = Chapter.query.filter_by(novel_id=novel.id).limit(3).all()
        
        if not chapters:
            print("Главы не найдены")
            return
        
        print(f"Тестирование рендеринга для новеллы: {novel.title}")
        
        for chapter in chapters:
            print(f"\nГлава {chapter.chapter_number}: {chapter.status}")
            
            # Тестируем фильтры
            color = app.jinja_env.filters['status_color'](chapter.status, 'chapter')
            badge_class = app.jinja_env.filters['status_badge_class'](chapter.status, 'chapter')
            icon = app.jinja_env.filters['status_icon'](chapter.status, 'chapter')
            text = app.jinja_env.filters['status_text'](chapter.status, 'chapter')
            
            print(f"  color: {color}")
            print(f"  badge_class: {badge_class}")
            print(f"  icon: {icon}")
            print(f"  text: {text}")
            
            # Рендерим HTML
            template_code = """
            <span class="{{ chapter.status|status_badge_class('chapter') }}">
                <i class="{{ chapter.status|status_icon('chapter') }}"></i>
                {{ chapter.status|status_text('chapter') }}
            </span>
            """
            
            template = app.jinja_env.from_string(template_code)
            rendered = template.render(chapter=chapter)
            
            print(f"  HTML: {rendered}")


def main():
    """Основная функция"""
    
    print("=" * 60)
    print("🔍 ОТЛАДКА СТАТУСОВ ГЛАВ")
    print("=" * 60)
    
    try:
        debug_chapter_statuses()
        print("\n" + "=" * 60)
        test_filter_rendering()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main()) 