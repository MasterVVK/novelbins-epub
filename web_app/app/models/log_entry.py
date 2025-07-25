from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app import db


class LogEntry(db.Model):
    """Модель записи лога"""
    __tablename__ = 'log_entries'

    id = Column(Integer, primary_key=True)
    
    # Связи
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=True)
    novel_id = Column(Integer, ForeignKey('novels.id'), nullable=True)
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=True)
    
    # Основная информация
    level = Column(String(20), nullable=False)  # INFO, ERROR, WARNING, DEBUG
    message = Column(Text, nullable=False)
    module = Column(String(100))  # Модуль, где произошло событие
    function = Column(String(100))  # Функция
    
    # Дополнительные данные
    extra_data = Column(JSON)  # Дополнительные данные в JSON формате
    
    # Время
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    task = relationship('Task', back_populates='logs')
    novel = relationship('Novel')
    chapter = relationship('Chapter')
    
    def __repr__(self):
        return f'<LogEntry {self.level}: {self.message[:50]}...>'
    
    @property
    def is_error(self):
        """Проверка, является ли лог ошибкой"""
        return self.level.upper() in ['ERROR', 'CRITICAL']
    
    @property
    def is_warning(self):
        """Проверка, является ли лог предупреждением"""
        return self.level.upper() == 'WARNING'
    
    @property
    def is_info(self):
        """Проверка, является ли лог информационным"""
        return self.level.upper() == 'INFO'
    
    @property
    def is_debug(self):
        """Проверка, является ли лог отладочным"""
        return self.level.upper() == 'DEBUG'
    
    def to_dict(self):
        """Преобразование в словарь для JSON"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'novel_id': self.novel_id,
            'chapter_id': self.chapter_id,
            'level': self.level,
            'message': self.message,
            'module': self.module,
            'function': self.function,
            'extra_data': self.extra_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_error': self.is_error,
            'is_warning': self.is_warning,
            'is_info': self.is_info,
            'is_debug': self.is_debug
        } 