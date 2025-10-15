from app.models import SystemSettings
from typing import List, Optional


class SettingsService:
    """Сервис для работы с системными настройками"""

    @staticmethod
    def get_gemini_api_keys() -> List[str]:
        """Получить список API ключей Gemini

        Приоритет:
        1. Из таблицы AIModel (новая система)
        2. Из SystemSettings (старая система, для обратной совместимости)
        """
        # Пытаемся получить из AIModel
        try:
            from app.models import AIModel
            gemini_model = AIModel.query.filter_by(
                provider='gemini',
                is_active=True
            ).first()

            if gemini_model:
                keys = gemini_model.get_api_keys_list()
                if keys:
                    return keys
        except Exception:
            # Если таблица AIModel еще не создана или произошла ошибка
            pass

        # Fallback на старую систему через SystemSettings
        keys_str = SystemSettings.get_setting('gemini_api_keys', '')
        if not keys_str:
            return []

        # Разбиваем по строкам и убираем пустые
        keys = [key.strip() for key in keys_str.split('\n') if key.strip()]
        return keys
    
    @staticmethod
    def get_openai_api_key() -> Optional[str]:
        """Получить API ключ OpenAI

        Приоритет:
        1. Из таблицы AIModel (новая система)
        2. Из SystemSettings (старая система, для обратной совместимости)
        """
        # Пытаемся получить из AIModel
        try:
            from app.models import AIModel
            openai_model = AIModel.query.filter_by(
                provider='openai',
                is_active=True
            ).first()

            if openai_model and openai_model.api_key:
                return openai_model.api_key
        except Exception:
            pass

        # Fallback на старую систему
        return SystemSettings.get_setting('openai_api_key')
    
    @staticmethod
    def get_default_model() -> str:
        """Получить модель по умолчанию

        Приоритет:
        1. Из таблицы AIModel (is_default=True)
        2. Из SystemSettings (старая система)
        """
        # Пытаемся получить из AIModel
        try:
            from app.models import AIModel
            default_model = AIModel.query.filter_by(is_default=True, is_active=True).first()
            if default_model:
                return default_model.model_id  # Возвращаем model_id, НЕ id!
        except Exception:
            pass

        # Fallback на старую систему
        return SystemSettings.get_setting('default_model', 'gemini-2.5-flash')
    
    @staticmethod
    def get_default_translation_temperature() -> float:
        """Получить температуру перевода по умолчанию"""
        return float(SystemSettings.get_setting('default_translation_temperature', '0.1'))
    
    @staticmethod
    def get_default_editing_temperature() -> float:
        """Получить температуру редактирования по умолчанию"""
        return float(SystemSettings.get_setting('default_editing_temperature', '0.7'))
    
    @staticmethod
    def get_default_editing_quality_mode() -> str:
        """Получить режим качества редактирования по умолчанию"""
        return SystemSettings.get_setting('default_editing_quality_mode', 'balanced')
    
    @staticmethod
    def get_default_temperature() -> float:
        """Получить температуру по умолчанию (для обратной совместимости)"""
        return SettingsService.get_default_translation_temperature()
    
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
    
    @staticmethod
    def get_proxy_url() -> Optional[str]:
        """Получить URL прокси"""
        return SystemSettings.get_setting('proxy_url') 