#!/usr/bin/env python3
"""
Исправление обновления конфигурации all_chapters с flag_modified
"""
import sys
import os

# Добавляем пути
web_app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_app')
sys.path.insert(0, web_app_path)

from app import create_app, db
from app.models import Novel
from sqlalchemy.orm.attributes import flag_modified

app = create_app()

with app.app_context():
    # Проверяем новеллу с ID 3
    novel = db.session.get(Novel, 3)
    
    if novel:
        print(f"📚 Новелла: {novel.title}")
        print(f"🔧 Старая конфигурация: {novel.config}")
        
        # Обновляем конфигурацию правильно
        if novel.config is None:
            novel.config = {}
        
        novel.config['all_chapters'] = True
        novel.config['max_chapters'] = 5  # Для теста
        
        # Важно! Уведомляем SQLAlchemy о том, что JSON поле изменилось
        flag_modified(novel, 'config')
        
        db.session.add(novel)
        db.session.commit()
        
        print(f"✅ Новая конфигурация: {novel.config}")
        
        # Проверяем после коммита
        db.session.refresh(novel)
        print(f"🔄 После refresh: {novel.config}")
        
        all_chapters_enabled = novel.config.get('all_chapters', False) if novel.config else False
        print(f"   all_chapters_enabled: {all_chapters_enabled}")
        
        if all_chapters_enabled:
            print("🎉 Конфигурация обновлена успешно!")
        else:
            print("❌ Конфигурация не обновилась")
    else:
        print("❌ Новелла не найдена")