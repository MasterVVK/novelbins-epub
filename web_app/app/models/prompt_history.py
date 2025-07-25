from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app import db


class PromptHistory(db.Model):
    """Модель для сохранения истории промптов и ответов"""
    __tablename__ = 'prompt_history'

    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=False)
    
    # Тип промпта
    prompt_type = Column(String(50), nullable=False)  # translation, summary, terms_extraction
    
    # Промпты
    system_prompt = Column(Text, nullable=False)
    user_prompt = Column(Text, nullable=False)
    response = Column(Text)
    
    # Метаданные
    api_key_index = Column(Integer)
    model_used = Column(String(100))
    temperature = Column(db.Float)
    tokens_used = Column(Integer)
    finish_reason = Column(String(50))
    
    # Статус
    success = Column(db.Boolean, default=True)
    error_message = Column(Text)
    
    # Время выполнения
    execution_time = Column(db.Float)  # секунды
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    chapter = relationship('Chapter', back_populates='prompt_history')
    
    def __repr__(self):
        return f'<PromptHistory {self.prompt_type} for Chapter {self.chapter.chapter_number}>'
    
    @classmethod
    def save_prompt(cls, chapter_id: int, prompt_type: str, system_prompt: str, 
                   user_prompt: str, response: str = None, **kwargs):
        """Сохранение промпта в историю"""
        prompt = cls(
            chapter_id=chapter_id,
            prompt_type=prompt_type,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            **kwargs
        )
        db.session.add(prompt)
        db.session.commit()
        return prompt
    
    @classmethod
    def get_chapter_history(cls, chapter_id: int, prompt_type: str = None):
        """Получение истории промптов для главы"""
        query = cls.query.filter_by(chapter_id=chapter_id)
        if prompt_type:
            query = query.filter_by(prompt_type=prompt_type)
        return query.order_by(cls.created_at.desc()).all() 