from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app import db


class Novel(db.Model):
    """Модель новеллы"""
    __tablename__ = 'novels'

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    original_title = Column(String(255))
    author = Column(String(255))
    source_url = Column(String(500))
    source_type = Column(String(50), default='novelbins')  # novelbins, webnovel, etc.

    # Статистика
    total_chapters = Column(Integer, default=0)
    parsed_chapters = Column(Integer, default=0)
    translated_chapters = Column(Integer, default=0)
    edited_chapters = Column(Integer, default=0)

    # Статус
    status = Column(String(50), default='pending')  # pending, parsing, translating, editing, completed
    is_active = Column(Boolean, default=True)

    # Конфигурация
    config = Column(JSON)  # Настройки парсинга, перевода, редактуры
    
    # Связь с шаблоном промпта
    prompt_template_id = Column(Integer, ForeignKey('prompt_templates.id'), nullable=True)

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    chapters = relationship('Chapter', back_populates='novel', cascade='all, delete-orphan')
    glossary_items = relationship('GlossaryItem', back_populates='novel', cascade='all, delete-orphan')
    tasks = relationship('Task', back_populates='novel', cascade='all, delete-orphan')
    prompt_template = relationship('PromptTemplate', back_populates='novels')

    def __repr__(self):
        return f'<Novel {self.title}>'

    @property
    def parsing_progress_percentage(self):
        """Процент завершения парсинга"""
        if self.total_chapters == 0:
            return 0
        return round((self.parsed_chapters / self.total_chapters) * 100, 1)

    @property
    def progress_percentage(self):
        """Процент завершения перевода"""
        if self.total_chapters == 0:
            return 0
        return round((self.translated_chapters / self.total_chapters) * 100, 1)

    @property
    def editing_progress_percentage(self):
        """Процент завершения редактуры"""
        if self.translated_chapters == 0:
            return 0
        return round((self.edited_chapters / self.translated_chapters) * 100, 1)

    def update_stats(self):
        """Обновление статистики"""
        self.parsed_chapters = len([c for c in self.chapters if c.status == 'parsed'])
        self.translated_chapters = len([c for c in self.chapters if c.status == 'translated'])
        self.edited_chapters = len([c for c in self.chapters if c.status == 'edited'])
        self.total_chapters = len(self.chapters)

        # Обновление статуса
        if self.total_chapters == 0:
            self.status = 'pending'
        elif self.translated_chapters == self.total_chapters:
            self.status = 'completed'
        elif self.translated_chapters > 0:
            self.status = 'translating'
        else:
            self.status = 'parsing'
    
    def get_prompt_template(self):
        """Получение шаблона промпта для новеллы"""
        if self.prompt_template:
            return self.prompt_template
        return PromptTemplate.get_default_template()
    
    def soft_delete(self):
        """Мягкое удаление новеллы (деактивация)"""
        self.is_active = False
        self.status = 'deleted'
        return self
    
    def restore(self):
        """Восстановление новеллы"""
        self.is_active = True
        self.status = 'pending'
        return self 