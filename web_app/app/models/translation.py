from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app import db


class Translation(db.Model):
    """Модель перевода"""
    __tablename__ = 'translations'

    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=False)

    # Переведенный контент
    translated_title = Column(String(500))
    translated_text = Column(Text)
    summary = Column(Text)

    # Метаданные перевода
    translation_type = Column(String(50), default='initial')  # initial, edited, final
    api_used = Column(String(100))  # gemini, gpt, claude
    model_used = Column(String(100))

    # Качество
    quality_score = Column(Integer)  # 1-10
    quality_issues = Column(JSON)  # Список проблем

    # Время выполнения
    translation_time = Column(Float)  # секунды
    tokens_used = Column(Integer)

    # Контекст
    context_used = Column(JSON)  # Использованный контекст

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    chapter = relationship('Chapter', back_populates='translations')

    def __repr__(self):
        return f'<Translation {self.id} for Chapter {self.chapter.chapter_number}>'

    @property
    def is_latest(self):
        """Проверка, что это последний перевод"""
        return self == self.chapter.translations[-1] if self.chapter.translations else False 