"""
Модель для хранения конфигураций AI моделей
"""
from app import db
from datetime import datetime
import json


class AIModel(db.Model):
    """Конфигурация AI модели для перевода"""
    __tablename__ = 'ai_models'

    id = db.Column(db.Integer, primary_key=True)

    # Базовая информация
    name = db.Column(db.String(100), nullable=False, unique=True)  # Отображаемое имя
    model_id = db.Column(db.String(100), nullable=False)  # ID модели для API
    description = db.Column(db.Text)

    # Провайдер API
    provider = db.Column(db.String(50), nullable=False)  # gemini, openai, anthropic, ollama, etc.
    api_type = db.Column(db.String(50))  # google-ai, google-vertex, openai-compatible, etc.

    # Настройки подключения
    api_endpoint = db.Column(db.String(500))  # URL для API (особенно для Ollama)
    api_key_required = db.Column(db.Boolean, default=True)
    api_key = db.Column(db.Text)  # Один API ключ (для провайдеров с одним ключом)
    api_keys = db.Column(db.JSON)  # Список API ключей (для Gemini с ротацией)

    # Параметры модели
    max_input_tokens = db.Column(db.Integer, default=30000)
    max_output_tokens = db.Column(db.Integer, default=8000)
    supports_system_prompt = db.Column(db.Boolean, default=True)
    supports_temperature = db.Column(db.Boolean, default=True)
    default_temperature = db.Column(db.Float, default=0.3)

    # Настройки для конкретных провайдеров
    provider_config = db.Column(db.JSON, default={})
    # Для Gemini: {"safety_settings": "block_none", "api_version": "v1beta"}
    # Для Ollama: {"model_file": "qwen2.5:32b", "keep_alive": "5m"}
    # Для OpenAI: {"organization": "org-xxx", "api_version": "v1"}

    # Характеристики производительности
    speed_rating = db.Column(db.Integer, default=3)  # 1-5, где 5 - самая быстрая
    quality_rating = db.Column(db.Integer, default=3)  # 1-5, где 5 - лучшее качество
    cost_rating = db.Column(db.Integer, default=3)  # 1-5, где 1 - самая дорогая

    # Рекомендации использования
    recommended_for = db.Column(db.JSON, default=[])  # ["dialogue", "description", "battle", etc.]
    not_recommended_for = db.Column(db.JSON, default=[])

    # Статус и метаданные
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_tested_at = db.Column(db.DateTime)
    test_status = db.Column(db.String(50))  # "success", "failed", "untested"

    def __repr__(self):
        return f'<AIModel {self.name} ({self.provider})>'

    def to_dict(self):
        """Преобразование в словарь для API"""
        return {
            'id': self.id,
            'name': self.name,
            'model_id': self.model_id,
            'description': self.description,
            'provider': self.provider,
            'api_type': self.api_type,
            'api_endpoint': self.api_endpoint,
            'api_key_required': self.api_key_required,
            'has_api_key': bool(self.api_key) or bool(self.api_keys),
            'api_keys_count': len(self.api_keys) if self.api_keys else (1 if self.api_key else 0),
            'max_input_tokens': self.max_input_tokens,
            'max_output_tokens': self.max_output_tokens,
            'supports_system_prompt': self.supports_system_prompt,
            'supports_temperature': self.supports_temperature,
            'default_temperature': self.default_temperature,
            'provider_config': self.provider_config or {},
            'speed_rating': self.speed_rating,
            'quality_rating': self.quality_rating,
            'cost_rating': self.cost_rating,
            'recommended_for': self.recommended_for or [],
            'not_recommended_for': self.not_recommended_for or [],
            'is_active': self.is_active,
            'is_default': self.is_default,
            'test_status': self.test_status,
            'last_tested_at': self.last_tested_at.isoformat() if self.last_tested_at else None
        }

    @classmethod
    def get_active_models(cls):
        """Получить все активные модели"""
        return cls.query.filter_by(is_active=True).all()

    @classmethod
    def get_by_provider(cls, provider):
        """Получить модели по провайдеру"""
        return cls.query.filter_by(provider=provider, is_active=True).all()

    @classmethod
    def get_default(cls):
        """Получить модель по умолчанию"""
        return cls.query.filter_by(is_default=True, is_active=True).first()

    def test_connection(self):
        """Тестировать подключение к модели"""
        # TODO: Реализовать тестирование в зависимости от провайдера
        pass

    def get_api_config(self):
        """Получить конфигурацию для API клиента"""
        config = {
            'model_id': self.model_id,
            'provider': self.provider,
            'api_type': self.api_type,
            'api_endpoint': self.api_endpoint,
            'max_output_tokens': self.max_output_tokens,
            'supports_system_prompt': self.supports_system_prompt,
            'default_temperature': self.default_temperature
        }

        # Добавляем ключи в зависимости от провайдера
        if self.api_keys:
            # Для провайдеров с ротацией ключей (Gemini)
            config['api_keys'] = self.api_keys
        elif self.api_key:
            # Для провайдеров с одним ключом
            config['api_key'] = self.api_key

        # Добавляем специфичные настройки провайдера
        if self.provider_config:
            config.update(self.provider_config)

        return config

    def get_api_keys_list(self):
        """Получить список API ключей для ротации"""
        if self.api_keys:
            return self.api_keys
        elif self.api_key:
            return [self.api_key]
        return []


# Предустановленные конфигурации моделей
DEFAULT_MODELS = [
    {
        'name': 'Gemini 2.5 Flash (Google AI)',
        'model_id': 'gemini-2.5-flash',
        'provider': 'gemini',
        'api_type': 'google-ai',
        'description': 'Быстрая и экономичная модель от Google',
        'api_endpoint': 'https://generativelanguage.googleapis.com/v1beta',
        'max_input_tokens': 1000000,
        'max_output_tokens': 256000,
        'speed_rating': 5,
        'quality_rating': 3,
        'cost_rating': 5,
        'recommended_for': ['draft', 'bulk_translation', 'battle_scenes'],
        'provider_config': {'api_version': 'v1beta', 'safety_settings': 'block_none'}
    },
    {
        'name': 'Gemini 2.5 Pro (Google AI)',
        'model_id': 'gemini-2.5-pro',
        'provider': 'gemini',
        'api_type': 'google-ai',
        'description': 'Продвинутая модель с балансом скорости и качества',
        'api_endpoint': 'https://generativelanguage.googleapis.com/v1beta',
        'max_input_tokens': 2000000,
        'max_output_tokens': 256000,
        'speed_rating': 3,
        'quality_rating': 4,
        'cost_rating': 3,
        'recommended_for': ['final_translation', 'complex_dialogue', 'cultural_content'],
        'provider_config': {'api_version': 'v1beta', 'safety_settings': 'block_none'}
    },
    {
        'name': 'GPT-4o',
        'model_id': 'gpt-4o',
        'provider': 'openai',
        'api_type': 'openai',
        'description': 'Последняя модель от OpenAI с отличным пониманием контекста',
        'api_endpoint': 'https://api.openai.com/v1',
        'max_input_tokens': 128000,
        'max_output_tokens': 16384,
        'speed_rating': 2,
        'quality_rating': 5,
        'cost_rating': 1,
        'recommended_for': ['poetry', 'emotional_scenes', 'complex_dialogue'],
        'provider_config': {'api_version': 'v1'}
    },
    {
        'name': 'Claude 3.5 Sonnet',
        'model_id': 'claude-3-5-sonnet-20241022',
        'provider': 'anthropic',
        'api_type': 'anthropic',
        'description': 'Модель от Anthropic с превосходной работой с длинным контекстом',
        'api_endpoint': 'https://api.anthropic.com/v1',
        'max_input_tokens': 200000,
        'max_output_tokens': 8192,
        'speed_rating': 3,
        'quality_rating': 5,
        'cost_rating': 2,
        'recommended_for': ['long_context', 'series_translation', 'analytical_content'],
        'provider_config': {'api_version': '2023-06-01', 'anthropic_version': '2023-06-01'}
    },
    {
        'name': 'Llama 3.1 8B (Ollama)',
        'model_id': 'llama3.1:8b',
        'provider': 'ollama',
        'api_type': 'ollama',
        'description': 'Быстрая и эффективная модель для общих задач',
        'api_endpoint': 'http://localhost:11434/api',
        'api_key_required': False,
        'max_input_tokens': 8192,
        'max_output_tokens': 4096,
        'speed_rating': 4,
        'quality_rating': 3,
        'cost_rating': 5,
        'recommended_for': ['fast_translation', 'dialogue', 'simple_text'],
        'provider_config': {
            'keep_alive': '5m',
            # Параметры для быстрой модели - позволяем больше генерации
            'safety_buffer': 0.15,          # 15% буфера (меньше для быстрой модели)
            'min_generation_ratio': 0.2,    # 20% минимум для генерации
            'max_generation_ratio': 0.6,    # 60% максимум для генерации
            'min_context_size': 2048        # Меньший минимальный контекст
        }
    },
    {
        'name': 'Mistral 7B (Ollama)',
        'model_id': 'mistral:7b',
        'provider': 'ollama',
        'api_type': 'ollama',
        'description': 'Сбалансированная модель с хорошим качеством',
        'api_endpoint': 'http://localhost:11434/api',
        'api_key_required': False,
        'max_input_tokens': 32768,
        'max_output_tokens': 16384,
        'speed_rating': 3,
        'quality_rating': 4,
        'cost_rating': 5,
        'recommended_for': ['balanced_translation', 'descriptive_text', 'character_dialogue'],
        'provider_config': {
            'keep_alive': '10m',
            # Параметры для сбалансированной модели
            'safety_buffer': 0.25,          # 25% буфера
            'min_generation_ratio': 0.12,   # 12% минимум
            'max_generation_ratio': 0.45,   # 45% максимум
            'min_context_size': 4096
        }
    },
    {
        'name': 'Yi 34B (Ollama)',
        'model_id': 'yi:34b',
        'provider': 'ollama',
        'api_type': 'ollama',
        'description': 'Мощная модель с большим контекстом для сложных переводов',
        'api_endpoint': 'http://localhost:11434/api',
        'api_key_required': False,
        'max_input_tokens': 200000,
        'max_output_tokens': 32768,
        'speed_rating': 2,
        'quality_rating': 5,
        'cost_rating': 5,
        'recommended_for': ['complex_narrative', 'literary_translation', 'long_context'],
        'provider_config': {
            'keep_alive': '15m',
            # Параметры для мощной модели - консервативные для стабильности
            'safety_buffer': 0.3,           # 30% буфера (больше для сложных задач)
            'min_generation_ratio': 0.1,    # 10% минимум
            'max_generation_ratio': 0.35,   # 35% максимум (консервативно)
            'min_context_size': 8192        # Большой минимальный контекст
        }
    },
    {
        'name': 'Qwen 2.5 32B (Ollama)',
        'model_id': 'qwen2.5:32b',
        'provider': 'ollama',
        'api_type': 'ollama',
        'description': 'Локальная модель с поддержкой китайского языка',
        'api_endpoint': 'http://localhost:11434/api',
        'api_key_required': False,
        'max_input_tokens': 32768,
        'max_output_tokens': 8192,
        'speed_rating': 2,
        'quality_rating': 4,
        'cost_rating': 5,  # Бесплатная локальная
        'recommended_for': ['chinese_content', 'privacy_sensitive', 'offline_work'],
        'provider_config': {
            'keep_alive': '5m',
            # 🔧 НОВЫЕ ПАРАМЕТРЫ ДЛЯ ДИНАМИЧЕСКОГО РАСЧЕТА num_predict
            'safety_buffer': 0.2,           # 20% буфер для промпта
            'min_generation_ratio': 0.15,   # Минимум 15% от контекста для генерации
            'max_generation_ratio': 0.4,    # Максимум 40% от контекста для генерации  
            'min_context_size': 4096        # Минимальный размер контекста для стабильности
        }
    }
]