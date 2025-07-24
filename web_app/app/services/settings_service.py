from app.models import SystemSettings
from typing import List, Optional


class SettingsService:
    """Сервис для работы с системными настройками"""
    
    @staticmethod
    def get_gemini_api_keys() -> List[str]:
        """Получить список API ключей Gemini"""
        keys_str = SystemSettings.get_setting('gemini_api_keys', '')
        if not keys_str:
            return []
        
        # Разбиваем по строкам и убираем пустые
        keys = [key.strip() for key in keys_str.split('\n') if key.strip()]
        return keys
    
    @staticmethod
    def get_openai_api_key() -> Optional[str]:
        """Получить API ключ OpenAI"""
        return SystemSettings.get_setting('openai_api_key')
    
    @staticmethod
    def get_default_model() -> str:
        """Получить модель по умолчанию"""
        return SystemSettings.get_setting('default_model', 'gemini-2.5-flash-preview-05-20')
    
    @staticmethod
    def get_default_temperature() -> float:
        """Получить температуру по умолчанию"""
        return float(SystemSettings.get_setting('default_temperature', '0.1'))
    
    @staticmethod
    def get_max_tokens() -> int:
        """Получить максимум токенов"""
        return int(SystemSettings.get_setting('max_tokens', '24000'))
    
    @staticmethod
    def get_request_delay() -> float:
        """Получить задержку запросов"""
        return float(SystemSettings.get_setting('request_delay', '1.0'))
    
    @staticmethod
    def get_max_chapters() -> int:
        """Получить максимум глав"""
        return int(SystemSettings.get_setting('max_chapters', '10'))
    
    @staticmethod
    def get_quality_threshold() -> int:
        """Получить порог качества"""
        return int(SystemSettings.get_setting('quality_threshold', '7'))
    
    @staticmethod
    def get_next_gemini_key() -> Optional[str]:
        """Получить следующий доступный ключ Gemini (для ротации)"""
        keys = SettingsService.get_gemini_api_keys()
        if not keys:
            return None
        
        # Простая ротация - можно улучшить
        from datetime import datetime
        current_hour = datetime.now().hour
        return keys[current_hour % len(keys)]
    
    @staticmethod
    def has_api_keys() -> bool:
        """Проверить, есть ли API ключи"""
        gemini_keys = SettingsService.get_gemini_api_keys()
        openai_key = SettingsService.get_openai_api_key()
        return bool(gemini_keys or openai_key) 