#!/usr/bin/env python3
"""
Отладка конфигурации all_chapters
"""
import sys
import os

# Добавляем пути
web_app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_app')
sys.path.insert(0, web_app_path)

from app import create_app, db
from app.models import Novel

app = create_app()

with app.app_context():
    # Проверяем новеллу с ID 3
    novel = db.session.get(Novel, 3)
    
    if novel:
        print(f"📚 Новелла: {novel.title}")
        print(f"🔧 Конфигурация: {novel.config}")
        print(f"🔧 Тип конфигурации: {type(novel.config)}")
        
        if novel.config:
            print(f"🔧 all_chapters: {novel.config.get('all_chapters')}")
            print(f"🔧 all_chapters тип: {type(novel.config.get('all_chapters'))}")
            print(f"🔧 max_chapters: {novel.config.get('max_chapters')}")
            
            # Тестируем различные способы проверки
            print("\n🧪 ТЕСТЫ ПРОВЕРКИ:")
            all_chapters_enabled = novel.config.get('all_chapters', False) if novel.config else False
            print(f"   all_chapters_enabled: {all_chapters_enabled} (тип: {type(all_chapters_enabled)})")
            
            # Попробуем прямое присвоение
            print("\n🔄 Попытка обновления конфигурации...")
            novel.config['all_chapters'] = True
            db.session.add(novel)
            db.session.commit()
            
            print(f"✅ Обновлено: {novel.config}")
            
            # Проверяем после коммита
            db.session.refresh(novel)
            print(f"🔄 После refresh: {novel.config}")
            
            all_chapters_enabled = novel.config.get('all_chapters', False) if novel.config else False
            print(f"   all_chapters_enabled после обновления: {all_chapters_enabled}")
        else:
            print("❌ Конфигурация отсутствует")
    else:
        print("❌ Новелла не найдена")