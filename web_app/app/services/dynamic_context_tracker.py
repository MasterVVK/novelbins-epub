"""
Модуль для сбора и предоставления статистики динамического контекста
"""
from datetime import datetime, timezone
from app.models import AIModel

class DynamicContextTracker:
    """Слежение за использовать динамического контекста"""
    
    def __init__(self):
        self.last_context_size = None
        self.original_context_size = None
        self.usage_count = 0
        self.total_savings_tokens = 0
        self.last_update = None
        self.model_name = None
    
    def record_usage(self, model_name: str, original_context: int, dynamic_context: int):
        """Записать использование динамического контекста"""
        self.model_name = model_name
        self.original_context_size = original_context
        self.last_context_size = dynamic_context
        self.usage_count += 1
        self.total_savings_tokens += (original_context - dynamic_context)
        self.last_update = datetime.now(timezone.utc)
    
    def get_stats(self) -> dict:
        """Получить текущую статистику"""
        if not self.last_context_size:
            return None
        
        savings_percent = (self.original_context_size - self.last_context_size) / self.original_context_size * 100
        
        return {
            'model_name': self.model_name,
            'last_context_size': self.last_context_size,
            'original_context_size': self.original_context_size,
            'savings_percent': savings_percent,
            'savings_tokens': self.total_savings_tokens,
            'usage_count': self.usage_count,
            'last_update': self.last_update.isoformat(),
            'current_savings_tokens': self.original_context_size - self.last_context_size,
            'memory_saved_mb': self.total_savings_tokens * 3 / 1024  # ~3 байта на токен
        }


# Глобальный инстанс трекера
tracker = DynamicContextTracker()