from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app import db


class Task(db.Model):
    """Модель задачи"""
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    novel_id = Column(Integer, ForeignKey('novels.id'), nullable=False)
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=True)

    # Основная информация
    task_type = Column(String(50), nullable=False)  # parse, translate, edit, generate_epub
    status = Column(String(50), default='pending')  # pending, running, completed, failed

    # Прогресс
    progress = Column(Float, default=0.0)  # 0.0 - 1.0
    current_step = Column(String(100))
    total_steps = Column(Integer, default=1)

    # Результат
    result = Column(JSON)  # Результат выполнения
    error_message = Column(Text)  # Сообщение об ошибке

    # Время выполнения
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration = Column(Float)  # секунды

    # Приоритет
    priority = Column(Integer, default=5)  # 1-10, где 1 - высший приоритет

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    novel = relationship('Novel', back_populates='tasks')
    chapter = relationship('Chapter')
    logs = relationship('LogEntry', back_populates='task', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Task {self.task_type} for {self.novel.title}>'

    @property
    def is_completed(self):
        """Проверка завершения"""
        return self.status == 'completed'

    @property
    def is_failed(self):
        """Проверка ошибки"""
        return self.status == 'failed'

    @property
    def is_running(self):
        """Проверка выполнения"""
        return self.status == 'running'

    def start(self):
        """Запуск задачи"""
        self.status = 'running'
        self.started_at = datetime.utcnow()

    def complete(self, result=None):
        """Завершение задачи"""
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        self.progress = 1.0
        if result:
            self.result = result
        if self.started_at:
            self.duration = (self.completed_at - self.started_at).total_seconds()

    def fail(self, error_message):
        """Ошибка задачи"""
        self.status = 'failed'
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        if self.started_at:
            self.duration = (self.completed_at - self.started_at).total_seconds()

    def update_progress(self, progress, step=None):
        """Обновление прогресса"""
        self.progress = min(1.0, max(0.0, progress))
        if step:
            self.current_step = step 