#!/usr/bin/env python3
"""
Скрипт для просмотра всех настроек системы
"""
from app import create_app, db
from app.models import SystemSettings
from app.services.settings_service import SettingsService

def main():
    app = create_app()
    with app.app_context():
        print("🔧 НАСТРОЙКИ СИСТЕМЫ")
        print("=" * 50)
        
        # Получаем все настройки
        all_settings = SystemSettings.query.all()
        
        if not all_settings:
            print("❌ Настроек не найдено")
            return
        
        for setting in all_settings:
            print(f"📝 {setting.key}:")
            print(f"   Значение: {setting.value}")
            print(f"   Описание: {setting.description}")
            print(f"   Обновлено: {setting.updated_at}")
            print()
        
        print("🔑 API КЛЮЧИ")
        print("=" * 30)
        
        gemini_keys = SettingsService.get_gemini_api_keys()
        openai_key = SettingsService.get_openai_api_key()
        
        print(f"Gemini ключей: {len(gemini_keys)}")
        if gemini_keys:
            for i, key in enumerate(gemini_keys, 1):
                print(f"  {i}. {key[:10]}...{key[-4:]}")
        
        print(f"OpenAI ключ: {'✅' if openai_key else '❌'}")
        if openai_key:
            print(f"  {openai_key[:10]}...{openai_key[-4:]}")
        
        print()
        print("⚙️ ПАРАМЕТРЫ")
        print("=" * 20)
        print(f"Модель по умолчанию: {SettingsService.get_default_model()}")
        print(f"Температура: {SettingsService.get_default_temperature()}")
        print(f"Максимум токенов: {SettingsService.get_max_tokens()}")
        print(f"Задержка запросов: {SettingsService.get_request_delay()} сек")
        print(f"Максимум глав: {SettingsService.get_max_chapters()}")
        print(f"Порог качества: {SettingsService.get_quality_threshold()}")

if __name__ == "__main__":
    main() 