"""
Модуль для работы с консольным буфером (Redis-backed)
"""
from datetime import datetime
from typing import List, Dict, Any
import json
import redis
import os

# Подключение к Redis
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=1,  # Используем ту же БД что и Celery
    decode_responses=True
)

MAX_BUFFER_SIZE = 1000
BUFFER_KEY = 'console:messages'

def add_console_message(message: str, level: str = 'INFO', source: str = 'console') -> Dict[str, Any]:
    """Добавляет сообщение в консольный буфер (Redis)"""
    timestamp = datetime.now().isoformat()
    console_message = {
        'timestamp': timestamp,
        'level': level,
        'message': message,
        'source': source
    }

    try:
        # Добавляем в Redis list
        redis_client.rpush(BUFFER_KEY, json.dumps(console_message, ensure_ascii=False))

        # Ограничиваем размер буфера
        redis_client.ltrim(BUFFER_KEY, -MAX_BUFFER_SIZE, -1)
    except Exception as e:
        print(f"Ошибка записи в console buffer: {e}")

    return console_message

def get_console_buffer() -> List[Dict[str, Any]]:
    """Возвращает копию консольного буфера из Redis"""
    try:
        messages = redis_client.lrange(BUFFER_KEY, 0, -1)
        return [json.loads(msg) for msg in messages]
    except Exception as e:
        print(f"Ошибка чтения console buffer: {e}")
        return []

def clear_console_buffer():
    """Очищает консольный буфер в Redis"""
    try:
        redis_client.delete(BUFFER_KEY)
    except Exception as e:
        print(f"Ошибка очистки console buffer: {e}")

def get_console_stats() -> Dict[str, Any]:
    """Возвращает статистику консольного буфера"""
    levels = {}
    sources = {}
    
    for log in console_buffer:
        level = log['level']
        source = log['source']
        
        levels[level] = levels.get(level, 0) + 1
        sources[source] = sources.get(source, 0) + 1
    
    return {
        'total': len(console_buffer),
        'levels': levels,
        'sources': sources,
        'buffer_size': len(console_buffer),
        'max_buffer_size': MAX_BUFFER_SIZE
    } 