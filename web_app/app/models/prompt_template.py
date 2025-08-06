from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app import db


class PromptTemplate(db.Model):
    """Модель шаблона промпта для перевода"""
    __tablename__ = 'prompt_templates'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Категория шаблона
    category = Column(String(50), default='general')  # general, xianxia, wuxia, modern, etc.
    
    # Основные промпты
    translation_prompt = Column(Text, nullable=False)
    summary_prompt = Column(Text)
    terms_extraction_prompt = Column(Text)
    
    # Промпты редактуры
    editing_analysis_prompt = Column(Text)
    editing_style_prompt = Column(Text)
    editing_dialogue_prompt = Column(Text)
    editing_final_prompt = Column(Text)
    
    # Настройки
    temperature = Column(db.Float, default=0.1)
    max_tokens = Column(Integer, default=24000)
    
    # Метаданные
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    novels = relationship('Novel', back_populates='prompt_template')
    
    def __repr__(self):
        return f'<PromptTemplate {self.name}>'
    
    @classmethod
    def get_default_template(cls):
        """Получение шаблона по умолчанию"""
        return cls.query.filter_by(is_default=True, is_active=True).first()
    
    @classmethod
    def get_templates_by_category(cls, category):
        """Получение шаблонов по категории"""
        return cls.query.filter_by(category=category, is_active=True).all()
    
    def copy(self, new_name=None):
        """Создание копии шаблона"""
        if not new_name:
            new_name = f"{self.name} (копия)"
        
        new_template = PromptTemplate(
            name=new_name,
            description=self.description,
            category=self.category,
            translation_prompt=self.translation_prompt,
            summary_prompt=self.summary_prompt,
            terms_extraction_prompt=self.terms_extraction_prompt,
            editing_analysis_prompt=self.editing_analysis_prompt,
            editing_style_prompt=self.editing_style_prompt,
            editing_dialogue_prompt=self.editing_dialogue_prompt,
            editing_final_prompt=self.editing_final_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            is_default=False
        )
        
        return new_template 