#!/usr/bin/env python3
"""
Финальный тест функционала "все главы" с исправленной конфигурацией
"""
import sys
import os

# Добавляем пути
web_app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_app')
sys.path.insert(0, web_app_path)

from app import create_app, db
from app.models import Novel
from app.services.parser_service import WebParserService
from sqlalchemy.orm.attributes import flag_modified

app = create_app()

with app.app_context():
    # Проверяем новеллу с ID 3
    novel = db.session.get(Novel, 3)
    
    if novel:
        print(f"📚 Новелла: {novel.title}")
        print(f"🔧 Текущая конфигурация: {novel.config}")
        
        # Тест 1: режим "все главы"
        print("\n🎯 ТЕСТ 1: Режим 'все главы'")
        print("=" * 40)
        
        novel.config['all_chapters'] = True
        novel.config['max_chapters'] = 3  # Должен игнорироваться
        flag_modified(novel, 'config')
        db.session.add(novel)
        db.session.commit()
        
        print(f"⚙️ Установлена конфигурация: all_chapters=True, max_chapters=3")
        
        parser_service = WebParserService()
        chapters_all = parser_service.parse_novel_chapters(novel)
        
        print(f"✅ Результат: получено {len(chapters_all) if chapters_all else 0} глав")
        
        # Тест 2: режим с ограничением
        print("\n🎯 ТЕСТ 2: Режим с ограничением max_chapters=3")
        print("=" * 40)
        
        novel.config['all_chapters'] = False
        novel.config['max_chapters'] = 3
        flag_modified(novel, 'config')
        db.session.add(novel)
        db.session.commit()
        
        print(f"⚙️ Установлена конфигурация: all_chapters=False, max_chapters=3")
        
        chapters_limited = parser_service.parse_novel_chapters(novel)
        
        print(f"✅ Результат: получено {len(chapters_limited) if chapters_limited else 0} глав")
        
        # Сравнение результатов
        print("\n📊 СРАВНЕНИЕ РЕЗУЛЬТАТОВ:")
        print("=" * 40)
        if chapters_all and chapters_limited:
            print(f"   Режим 'все главы': {len(chapters_all)} глав")
            print(f"   Режим 'max_chapters=3': {len(chapters_limited)} глав")
            
            if len(chapters_all) > len(chapters_limited):
                print("🎉 ТЕСТ ПРОЙДЕН! Функционал работает корректно!")
                print(f"   Разница: {len(chapters_all) - len(chapters_limited)} дополнительных глав")
                
                print("\n📋 Образцы глав:")
                print("   Режим 'все главы' (первые 5):")
                for i, chapter in enumerate(chapters_all[:5], 1):
                    print(f"      {i}. {chapter['title']}")
                    
                print("   Режим 'max_chapters=3':")
                for i, chapter in enumerate(chapters_limited, 1):
                    print(f"      {i}. {chapter['title']}")
            else:
                print("❌ ТЕСТ НЕ ПРОЙДЕН! Количество глав одинаково")
        else:
            print("❌ Ошибка получения глав в одном из режимов")
        
        # Восстанавливаем исходную конфигурацию
        novel.config['all_chapters'] = False
        novel.config['max_chapters'] = 2
        flag_modified(novel, 'config') 
        db.session.add(novel)
        db.session.commit()
        print("\n🔄 Исходная конфигурация восстановлена")
        
    else:
        print("❌ Новелла не найдена")
        
print("\n🏁 Финальный тест завершен!")