"""
Сервис для работы с логами
"""
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy import desc
from app.models import LogEntry, Task, Novel, Chapter
from app import db, socketio

# Импортируем функцию для консольного вывода
try:
    from app.utils.console_buffer import add_console_message
except ImportError:
    # Если модуль еще не импортирован, создаем заглушку
    def add_console_message(message, level='INFO', source='console'):
        pass


class DatabaseHandler(logging.Handler):
    """Хендлер для сохранения логов в базу данных"""
    
    def __init__(self, task_id: Optional[int] = None, novel_id: Optional[int] = None, 
                 chapter_id: Optional[int] = None):
        super().__init__()
        self.task_id = task_id
        self.novel_id = novel_id
        self.chapter_id = chapter_id
    
    def emit(self, record):
        try:
            # Получаем информацию о модуле и функции
            module = record.module if hasattr(record, 'module') else None
            function = record.funcName if hasattr(record, 'funcName') else None
            
            # Создаем запись лога
            log_entry = LogEntry(
                task_id=self.task_id,
                novel_id=self.novel_id,
                chapter_id=self.chapter_id,
                level=record.levelname,
                message=record.getMessage(),
                module=module,
                function=function,
                extra_data=getattr(record, 'extra_data', None)
            )
            
            # Сохраняем в базу данных
            db.session.add(log_entry)
            db.session.commit()
            
            # Отправляем через WebSocket
            self._emit_websocket(log_entry)
            
        except Exception as e:
            # Если не удалось сохранить лог, выводим в консоль
            print(f"Ошибка сохранения лога: {e}")
    
    def _emit_websocket(self, log_entry: LogEntry):
        """Отправка лога через WebSocket"""
        try:
            socketio.emit('log_entry', log_entry.to_dict())
        except Exception as e:
            print(f"Ошибка отправки лога через WebSocket: {e}")


class LogService:
    """Сервис для работы с логами"""
    
    @staticmethod
    def get_logger(task_id: Optional[int] = None, novel_id: Optional[int] = None, 
                   chapter_id: Optional[int] = None) -> logging.Logger:
        """Получение логгера с сохранением в базу данных"""
        logger = logging.getLogger(f"task_{task_id}" if task_id else "general")
        
        # Добавляем хендлер для базы данных
        db_handler = DatabaseHandler(task_id, novel_id, chapter_id)
        db_handler.setLevel(logging.INFO)
        
        # Форматтер
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
        db_handler.setFormatter(formatter)
        
        # Добавляем хендлер, если его еще нет
        if not any(isinstance(h, DatabaseHandler) for h in logger.handlers):
            logger.addHandler(db_handler)
        
        return logger
    
    @staticmethod
    def log_info(message: str, task_id: Optional[int] = None, novel_id: Optional[int] = None,
                 chapter_id: Optional[int] = None, extra_data: Optional[Dict] = None):
        """Логирование информационного сообщения"""
        logger = LogService.get_logger(task_id, novel_id, chapter_id)
        if extra_data:
            logger.info(message, extra={'extra_data': extra_data})
        else:
            logger.info(message)
        
        # Отправляем в консоль
        source = 'system'
        if task_id:
            task = Task.query.get(task_id)
            if task and task.task_type:
                source = task.task_type
        elif novel_id:
            # Определяем источник на основе контекста
            if 'редактур' in message.lower() or 'отредактирован' in message.lower():
                source = 'editor'
            elif 'перевод' in message.lower() or 'переведен' in message.lower():
                source = 'translator'
            elif 'парсинг' in message.lower() or 'обработк' in message.lower():
                source = 'parser'
            else:
                source = 'system'
        add_console_message(message, 'INFO', source)
    
    @staticmethod
    def log_error(message: str, task_id: Optional[int] = None, novel_id: Optional[int] = None,
                  chapter_id: Optional[int] = None, extra_data: Optional[Dict] = None):
        """Логирование ошибки"""
        logger = LogService.get_logger(task_id, novel_id, chapter_id)
        if extra_data:
            logger.error(message, extra={'extra_data': extra_data})
        else:
            logger.error(message)
        
        # Отправляем в консоль
        source = 'system'
        if task_id:
            task = Task.query.get(task_id)
            if task and task.task_type:
                source = task.task_type
        elif novel_id:
            # Определяем источник на основе контекста
            if 'редактур' in message.lower() or 'отредактирован' in message.lower():
                source = 'editor'
            elif 'перевод' in message.lower() or 'переведен' in message.lower():
                source = 'translator'
            elif 'парсинг' in message.lower() or 'обработк' in message.lower():
                source = 'parser'
            else:
                source = 'system'
        add_console_message(message, 'ERROR', source)
    
    @staticmethod
    def log_warning(message: str, task_id: Optional[int] = None, novel_id: Optional[int] = None,
                    chapter_id: Optional[int] = None, extra_data: Optional[Dict] = None):
        """Логирование предупреждения"""
        logger = LogService.get_logger(task_id, novel_id, chapter_id)
        if extra_data:
            logger.warning(message, extra={'extra_data': extra_data})
        else:
            logger.warning(message)
        
        # Отправляем в консоль
        source = 'system'
        if task_id:
            task = Task.query.get(task_id)
            if task and task.task_type:
                source = task.task_type
        elif novel_id:
            # Определяем источник на основе контекста
            if 'редактур' in message.lower() or 'отредактирован' in message.lower():
                source = 'editor'
            elif 'перевод' in message.lower() or 'переведен' in message.lower():
                source = 'translator'
            elif 'парсинг' in message.lower() or 'обработк' in message.lower():
                source = 'parser'
            else:
                source = 'system'
        add_console_message(message, 'WARNING', source)
    
    @staticmethod
    def log_debug(message: str, task_id: Optional[int] = None, novel_id: Optional[int] = None,
                  chapter_id: Optional[int] = None, extra_data: Optional[Dict] = None):
        """Логирование отладочной информации"""
        logger = LogService.get_logger(task_id, novel_id, chapter_id)
        if extra_data:
            logger.debug(message, extra={'extra_data': extra_data})
        else:
            logger.debug(message)
        
        # Отправляем в консоль
        source = 'system'
        if task_id:
            task = Task.query.get(task_id)
            if task and task.task_type:
                source = task.task_type
        elif novel_id:
            # Определяем источник на основе контекста
            if 'редактур' in message.lower() or 'отредактирован' in message.lower():
                source = 'editor'
            elif 'перевод' in message.lower() or 'переведен' in message.lower():
                source = 'translator'
            elif 'парсинг' in message.lower() or 'обработк' in message.lower():
                source = 'parser'
            else:
                source = 'system'
        add_console_message(message, 'DEBUG', source)
    
    @staticmethod
    def get_logs(task_id: Optional[int] = None, novel_id: Optional[int] = None,
                 chapter_id: Optional[int] = None, level: Optional[str] = None,
                 limit: int = 100, offset: int = 0) -> List[LogEntry]:
        """Получение логов с фильтрацией"""
        query = LogEntry.query
        
        if task_id:
            query = query.filter(LogEntry.task_id == task_id)
        if novel_id:
            query = query.filter(LogEntry.novel_id == novel_id)
        if chapter_id:
            query = query.filter(LogEntry.chapter_id == chapter_id)
        if level:
            query = query.filter(LogEntry.level == level.upper())
        
        return query.order_by(desc(LogEntry.created_at)).offset(offset).limit(limit).all()
    
    @staticmethod
    def get_recent_logs(hours: int = 24, limit: int = 100) -> List[LogEntry]:
        """Получение недавних логов"""
        since = datetime.utcnow() - timedelta(hours=hours)
        return LogEntry.query.filter(
            LogEntry.created_at >= since
        ).order_by(desc(LogEntry.created_at)).limit(limit).all()
    
    @staticmethod
    def get_task_logs(task_id: int, limit: int = 100) -> List[LogEntry]:
        """Получение логов конкретной задачи"""
        return LogService.get_logs(task_id=task_id, limit=limit)
    
    @staticmethod
    def get_novel_logs(novel_id: int, limit: int = 100) -> List[LogEntry]:
        """Получение логов конкретной новеллы"""
        return LogService.get_logs(novel_id=novel_id, limit=limit)
    
    @staticmethod
    def get_error_logs(limit: int = 100) -> List[LogEntry]:
        """Получение только ошибок"""
        return LogEntry.query.filter(
            LogEntry.level.in_(['ERROR', 'CRITICAL'])
        ).order_by(desc(LogEntry.created_at)).limit(limit).all()
    
    @staticmethod
    def clear_old_logs(days: int = 30) -> int:
        """Очистка старых логов"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted = LogEntry.query.filter(LogEntry.created_at < cutoff_date).delete()
        db.session.commit()
        return deleted
    
    @staticmethod
    def get_log_stats() -> Dict[str, Any]:
        """Получение статистики логов"""
        total_logs = LogEntry.query.count()
        error_logs = LogEntry.query.filter(LogEntry.level.in_(['ERROR', 'CRITICAL'])).count()
        warning_logs = LogEntry.query.filter(LogEntry.level == 'WARNING').count()
        info_logs = LogEntry.query.filter(LogEntry.level == 'INFO').count()
        
        # Логи за последние 24 часа
        since_24h = datetime.utcnow() - timedelta(hours=24)
        recent_logs = LogEntry.query.filter(LogEntry.created_at >= since_24h).count()
        
        return {
            'total': total_logs,
            'errors': error_logs,
            'warnings': warning_logs,
            'info': info_logs,
            'recent_24h': recent_logs
        } 