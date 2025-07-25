from flask import Blueprint, request, jsonify, Response
import time
import json
from datetime import datetime, timedelta
from app.utils.console_buffer import (
    add_console_message, 
    get_console_buffer, 
    clear_console_buffer, 
    get_console_stats as get_buffer_stats
)

console_bp = Blueprint('console', __name__)

@console_bp.route('/console/logs', methods=['GET'])
def get_console_logs():
    """Получение консольных логов"""
    try:
        # Получаем параметры
        limit = request.args.get('limit', 100, type=int)
        level = request.args.get('level', None)
        source = request.args.get('source', None)
        
        # Фильтруем логи
        logs = get_console_buffer()
        
        if level:
            logs = [log for log in logs if log['level'] == level.upper()]
        
        if source:
            logs = [log for log in logs if log['source'] == source]
        
        # Возвращаем последние логи
        logs = logs[-limit:] if limit else logs
        
        return jsonify({
            'success': True,
            'logs': logs,
            'total': len(logs),
            'buffer_size': len(logs)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@console_bp.route('/console/stream', methods=['GET'])
def stream_console_logs():
    """Stream консольных логов в реальном времени"""
    def generate():
        buffer = get_console_buffer()
        last_index = len(buffer)
        
        while True:
            # Проверяем новые сообщения
            buffer = get_console_buffer()
            if len(buffer) > last_index:
                new_messages = buffer[last_index:]
                for message in new_messages:
                    yield f"data: {json.dumps(message)}\n\n"
                last_index = len(buffer)
            
            time.sleep(0.5)  # Пауза между проверками
    
    return Response(generate(), mimetype='text/event-stream')

@console_bp.route('/console/clear', methods=['POST'])
def clear_console():
    """Очистка консольного буфера"""
    clear_console_buffer()
    
    return jsonify({
        'success': True,
        'message': 'Консольный буфер очищен'
    })

@console_bp.route('/console/stats', methods=['GET'])
def get_console_stats():
    """Статистика консольных логов"""
    try:
        stats = get_buffer_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 