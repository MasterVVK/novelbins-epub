"""
Модуль для работы с консольным буфером
"""
from datetime import datetime
from typing import List, Dict, Any

# Буфер для хранения консольных сообщений
console_buffer: List[Dict[str, Any]] = []
MAX_BUFFER_SIZE = 1000

def add_console_message(message: str, level: str = 'INFO', source: str = 'console') -> Dict[str, Any]:
    """Добавляет сообщение в консольный буфер"""
    global console_buffer
    
    timestamp = datetime.now().isoformat()
    console_message = {
        'timestamp': timestamp,
        'level': level,
        'message': message,
        'source': source
    }
    
    console_buffer.append(console_message)
    
    # Ограничиваем размер буфера
    if len(console_buffer) > MAX_BUFFER_SIZE:
        console_buffer.pop(0)
    
    return console_message

def get_console_buffer() -> List[Dict[str, Any]]:
    """Возвращает копию консольного буфера"""
    return console_buffer.copy()

def clear_console_buffer():
    """Очищает консольный буфер"""
    global console_buffer
    console_buffer.clear()

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