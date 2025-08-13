#!/usr/bin/env python3
"""
Скрипт для обновления существующих шаблонов с промптами редактуры
"""

from app import create_app, db
from app.services.prompt_template_service import PromptTemplateService

def main():
    app = create_app()
    
    with app.app_context():
        print("🔄 Обновляем шаблоны промптов с поддержкой редактуры...")
        
        # Создаем/обновляем шаблоны
        PromptTemplateService.create_default_templates()
        
        print("✅ Шаблоны успешно обновлены!")
        print("\nТеперь доступны промпты редактуры:")
        print("- editing_analysis_prompt - анализ качества текста")
        print("- editing_style_prompt - улучшение стиля")
        print("- editing_dialogue_prompt - полировка диалогов")
        print("- editing_final_prompt - финальная полировка")

if __name__ == "__main__":
    main()