#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, Chapter, Translation, Task
from app.services.translator_service import TranslatorService
from app.services.editor_service import EditorService

app = create_app()

def test_editor_service():
    """Тестирование EditorService напрямую"""
    print("🔍 ТЕСТИРОВАНИЕ EDITORSERVICE")
    print("=" * 50)
    
    with app.app_context():
        # Получаем главу 3 (готова к редактуре)
        chapter = Chapter.query.filter_by(
            novel_id=2,
            chapter_number=3,
            is_active=True
        ).first()
        
        if not chapter:
            print("❌ Глава 3 не найдена")
            return
        
        print(f"📖 Глава: {chapter.original_title}")
        print(f"📊 Статус: {chapter.status}")
        print(f"📝 Переводов: {len(chapter.translations)}")
        
        if not chapter.current_translation:
            print("❌ Нет перевода для редактуры")
            return
        
        print(f"✅ Перевод найден: {len(chapter.current_translation.translated_text)} символов")
        
        # Инициализируем сервисы
        print("\n🚀 Инициализируем сервисы...")
        try:
            translator_service = TranslatorService()
            editor_service = EditorService(translator_service)
            print("✅ Сервисы инициализированы")
        except Exception as e:
            print(f"❌ Ошибка инициализации сервисов: {e}")
            return
        
        # Тестируем редактуру
        print(f"\n📝 Запускаем редактуру главы {chapter.chapter_number}...")
        try:
            success = editor_service.edit_chapter(chapter)
            if success:
                print("✅ Редактура завершена успешно!")
                
                # Проверяем результат
                if chapter.edited_translation:
                    print(f"📄 Отредактированный текст: {len(chapter.edited_translation.translated_text)} символов")
                    print(f"🔧 Тип: {chapter.edited_translation.translation_type}")
                    print(f"🤖 API: {chapter.edited_translation.api_used}")
                else:
                    print("❌ Отредактированный перевод не найден")
            else:
                print("❌ Редактура завершилась с ошибкой")
                
        except Exception as e:
            print(f"❌ Ошибка редактуры: {e}")
            import traceback
            print(f"📄 Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_editor_service() 