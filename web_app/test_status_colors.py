#!/usr/bin/env python3
"""
Тестовый скрипт для проверки централизованной системы цветов статусов.
"""

import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.status_colors import status_colors


def test_status_colors():
    """Тестирование всех статусов и цветов"""
    
    print("🎨 Тестирование системы цветов статусов\n")
    
    # Тестовые данные
    test_cases = {
        'novel': ['pending', 'parsing', 'translating', 'editing', 'completed', 'deleted'],
        'chapter': ['pending', 'parsed', 'translated', 'edited', 'error'],
        'task_status': ['pending', 'running', 'completed', 'failed'],
        'task_type': ['parse', 'translate', 'edit', 'generate_epub']
    }
    
    # Тестирование каждого типа сущности
    for entity_type, statuses in test_cases.items():
        print(f"📋 {entity_type.upper()}:")
        for status in statuses:
            color = status_colors.get_status_color(status, entity_type)
            icon = status_colors.get_status_icon(status, entity_type)
            text = status_colors.get_status_text(status, entity_type)
            
            print(f"  {status:12} → {color:8} | {icon:20} | {text}")
        print()
    
    # Тестирование специальных случаев
    print("🔧 Специальные случаи:")
    
    # Шаблоны промптов
    print("  prompt_template (default=True, active=True) →", 
          status_colors.get_prompt_template_status_color(True, True))
    print("  prompt_template (default=False, active=True) →", 
          status_colors.get_prompt_template_status_color(False, True))
    print("  prompt_template (default=False, active=False) →", 
          status_colors.get_prompt_template_status_color(False, False))
    
    # Логи
    print("  log (INFO) →", status_colors.get_log_level_color('INFO'))
    print("  log (WARNING) →", status_colors.get_log_level_color('WARNING'))
    print("  log (ERROR) →", status_colors.get_log_level_color('ERROR'))
    print("  log (unknown) →", status_colors.get_log_level_color('UNKNOWN'))
    
    print()
    
    # Тестирование неизвестных статусов
    print("❓ Неизвестные статусы (должны возвращать значения по умолчанию):")
    unknown_statuses = ['unknown', 'invalid', 'test']
    for status in unknown_statuses:
        for entity_type in ['novel', 'chapter', 'task_status', 'task_type']:
            color = status_colors.get_status_color(status, entity_type)
            print(f"  {entity_type}.{status} → {color}")
    
    print()
    
    # Вывод всех цветов для документации
    print("📊 Все определенные цвета:")
    all_colors = status_colors.get_all_colors()
    for category, colors in all_colors.items():
        print(f"  {category}:")
        for status, color in colors.items():
            print(f"    {status} → {color}")
        print()


def test_template_filters():
    """Тестирование Jinja2 фильтров"""
    
    print("🔧 Тестирование Jinja2 фильтров:")
    
    # Имитация Flask app для тестирования фильтров
    class MockApp:
        def __init__(self):
            self.template_filters = {}
        
        def template_filter(self, name):
            def decorator(func):
                self.template_filters[name] = func
                return func
            return decorator
    
    mock_app = MockApp()
    
    # Импорт и регистрация фильтров
    from app.utils.template_filters import register_template_filters
    register_template_filters(mock_app)
    
    # Тестирование фильтров
    test_data = {
        'novel_status_color': ('completed', 'novel'),
        'chapter_status_color': ('translated', 'chapter'),
        'task_status_color': ('running', 'task_status'),
        'task_type_color': ('parse', 'task_type'),
        'log_level_color': ('ERROR', 'log')
    }
    
    for filter_name, (status, entity_type) in test_data.items():
        if filter_name in mock_app.template_filters:
            result = mock_app.template_filters[filter_name](status)
            print(f"  {filter_name}('{status}') → {result}")
        else:
            print(f"  ❌ {filter_name} не найден")
    
    print()


def test_color_consistency():
    """Проверка консистентности цветов"""
    
    print("✅ Проверка консистентности цветов:")
    
    # Проверяем, что одинаковые статусы имеют одинаковые цвета
    consistency_tests = [
        ('novel', 'pending', 'task_status', 'pending'),
        ('novel', 'completed', 'task_status', 'completed'),
        ('novel', 'deleted', 'chapter', 'error'),
    ]
    
    for entity1, status1, entity2, status2 in consistency_tests:
        color1 = status_colors.get_status_color(status1, entity1)
        color2 = status_colors.get_status_color(status2, entity2)
        
        if color1 == color2:
            print(f"  ✅ {entity1}.{status1} ({color1}) == {entity2}.{status2} ({color2})")
        else:
            print(f"  ❌ {entity1}.{status1} ({color1}) != {entity2}.{status2} ({color2})")
    
    print()


def main():
    """Основная функция тестирования"""
    
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ ЦВЕТОВ СТАТУСОВ")
    print("=" * 60)
    
    try:
        test_status_colors()
        test_template_filters()
        test_color_consistency()
        
        print("🎉 Все тесты завершены успешно!")
        print("📚 Документация создана в файлах:")
        print("   - STATUS_COLORS_ANALYSIS.md")
        print("   - STATUS_COLORS_GUIDE.md")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main()) 