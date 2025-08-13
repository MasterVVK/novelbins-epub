#!/usr/bin/env python3
"""
Скрипт для обновления .env файла из настроек в БД
"""
import sys
import os
sys.path.insert(0, '/home/user/novelbins-epub/web_app')

from app import create_app
from app.models.settings import SystemSettings

def update_env_from_db():
    """Обновление .env файла из настроек в БД"""
    
    app = create_app()
    with app.app_context():
        # Получаем API ключи из БД
        gemini_keys_setting = SystemSettings.query.filter_by(key='gemini_api_keys').first()
        openai_key_setting = SystemSettings.query.filter_by(key='openai_api_key').first()
        
        if not gemini_keys_setting and not openai_key_setting:
            print("❌ API ключи не найдены в БД")
            return
        
        # Читаем текущий .env файл
        env_path = '/home/user/novelbins-epub/.env'
        env_lines = []
        
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_lines = f.readlines()
        
        # Обновляем или добавляем ключи
        updated = False
        gemini_updated = False
        openai_updated = False
        
        # Обрабатываем Gemini ключи
        if gemini_keys_setting and gemini_keys_setting.value:
            # Преобразуем многострочные ключи в формат через запятую
            keys = gemini_keys_setting.value.strip().replace('\n', ',').replace('\r', '')
            # Убираем лишние запятые
            keys = ','.join([k.strip() for k in keys.split(',') if k.strip()])
            
            # Ищем и обновляем существующую строку
            for i, line in enumerate(env_lines):
                if line.startswith('GEMINI_API_KEYS='):
                    env_lines[i] = f'GEMINI_API_KEYS={keys}\n'
                    gemini_updated = True
                    updated = True
                    break
            
            # Если не нашли, добавляем новую
            if not gemini_updated:
                env_lines.append(f'GEMINI_API_KEYS={keys}\n')
                updated = True
            
            print(f"✅ Gemini API ключи обновлены ({len(keys.split(','))} ключей)")
        
        # Обрабатываем OpenAI ключ
        if openai_key_setting and openai_key_setting.value:
            key = openai_key_setting.value.strip()
            
            # Ищем и обновляем существующую строку
            for i, line in enumerate(env_lines):
                if line.startswith('OPENAI_API_KEY='):
                    env_lines[i] = f'OPENAI_API_KEY={key}\n'
                    openai_updated = True
                    updated = True
                    break
            
            # Если не нашли, добавляем новую
            if not openai_updated:
                env_lines.append(f'OPENAI_API_KEY={key}\n')
                updated = True
            
            print(f"✅ OpenAI API ключ обновлен")
        
        # Записываем обновленный .env файл
        if updated:
            with open(env_path, 'w') as f:
                f.writelines(env_lines)
            print(f"\n✅ Файл .env обновлен: {env_path}")
            print("⚠️  Перезапустите приложение для применения изменений")
        else:
            print("ℹ️  Изменений не требуется")

if __name__ == '__main__':
    update_env_from_db()