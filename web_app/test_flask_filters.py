#!/usr/bin/env python3
"""
Тест для проверки работы фильтров в контексте Flask приложения.
"""

import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import create_app
from app.utils.status_colors import status_colors


def test_flask_filters():
    """Тестирование фильтров в контексте Flask"""
    
    print("🧪 Тестирование фильтров в контексте Flask\n")
    
    # Создаем тестовое приложение
    app = create_app('testing')
    
    with app.app_context():
        # Тестируем фильтры
        test_cases = [
            ('novel', 'completed', 'success'),
            ('novel', 'pending', 'secondary'),
            ('chapter', 'translated', 'primary'),
            ('chapter', 'error', 'danger'),
            ('task_status', 'running', 'warning'),
            ('task_status', 'failed', 'danger'),
            ('task_type', 'parse', 'info'),
            ('task_type', 'edit', 'warning'),
        ]
        
        print("📋 Тестирование фильтров:")
        for entity_type, status, expected_color in test_cases:
            # Тестируем фильтр status_color
            color = app.jinja_env.filters['status_color'](status, entity_type)
            result = "✅" if color == expected_color else "❌"
            print(f"  {result} {entity_type}.{status} → {color} (ожидалось: {expected_color})")
            
            # Тестируем фильтр status_badge_class
            badge_class = app.jinja_env.filters['status_badge_class'](status, entity_type)
            expected_class = f"badge bg-{expected_color}"
            result = "✅" if badge_class == expected_class else "❌"
            print(f"  {result} badge_class → {badge_class}")
            
            # Тестируем фильтр status_icon
            icon = app.jinja_env.filters['status_icon'](status, entity_type)
            print(f"  📌 icon → {icon}")
            
            # Тестируем фильтр status_text
            text = app.jinja_env.filters['status_text'](status, entity_type)
            print(f"  📝 text → {text}")
            print()
        
        # Тестируем специальные фильтры
        print("🔧 Специальные фильтры:")
        
        # novel_status_color
        color = app.jinja_env.filters['novel_status_color']('completed')
        print(f"  novel_status_color('completed') → {color}")
        
        # chapter_status_color
        color = app.jinja_env.filters['chapter_status_color']('translated')
        print(f"  chapter_status_color('translated') → {color}")
        
        # task_status_color
        color = app.jinja_env.filters['task_status_color']('running')
        print(f"  task_status_color('running') → {color}")
        
        # task_type_color
        color = app.jinja_env.filters['task_type_color']('parse')
        print(f"  task_type_color('parse') → {color}")
        
        # log_level_color
        color = app.jinja_env.filters['log_level_color']('ERROR')
        print(f"  log_level_color('ERROR') → {color}")
        
        print()
        
        # Тестируем рендеринг шаблона
        print("🎨 Тестирование рендеринга шаблона:")
        
        template_code = """
        <span class="{{ status|status_badge_class('novel') }}">
            <i class="{{ status|status_icon('novel') }}"></i>
            {{ status|status_text('novel') }}
        </span>
        """
        
        template = app.jinja_env.from_string(template_code)
        rendered = template.render(status='completed')
        
        print(f"  Рендеринг для status='completed':")
        print(f"  {rendered}")
        
        print()
        print("🎉 Все тесты Flask фильтров завершены!")


def main():
    """Основная функция тестирования"""
    
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ FLASK ФИЛЬТРОВ")
    print("=" * 60)
    
    try:
        test_flask_filters()
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main()) 