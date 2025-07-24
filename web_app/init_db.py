#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных
"""
import os
import sys

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.services.prompt_template_service import PromptTemplateService
from app.services.glossary_service import GlossaryService

def init_database():
    """Инициализация базы данных"""
    app = create_app()
    
    with app.app_context():
        print("🗄️ Создание таблиц базы данных...")
        
        # Создаем все таблицы
        db.create_all()
        print("✅ Таблицы созданы")
        
        # Создаем шаблоны промптов по умолчанию
        print("📝 Создание шаблонов промптов по умолчанию...")
        PromptTemplateService.create_default_templates()
        print("✅ Шаблоны промптов созданы")
        
        print("\n🎉 База данных успешно инициализирована!")
        print("\nДоступные шаблоны промптов:")
        templates = PromptTemplateService.get_all_templates()
        for template in templates:
            print(f"  - {template.name} ({template.category})")
            if template.is_default:
                print(f"    ⭐ Шаблон по умолчанию")

if __name__ == '__main__':
    init_database() 