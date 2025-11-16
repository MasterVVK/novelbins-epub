"""
Модель шаблонов промптов для двуязычного выравнивания
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from app import db


class BilingualPromptTemplate(db.Model):
    """
    Шаблон промпта для LLM-выравнивания китайского оригинала и русского перевода.
    Аналог PromptTemplate, но специализирован для двуязычности.
    """
    __tablename__ = 'bilingual_prompt_templates'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Категория шаблона
    category = Column(String(50), default='general')  # general, xianxia, wuxia, modern, sci-fi, etc.

    # Основной промпт для выравнивания
    alignment_prompt = Column(Text, nullable=False)

    # Системный промпт (опционально, для моделей поддерживающих system message)
    system_prompt = Column(Text)

    # Промпты для специфичных задач
    validation_prompt = Column(Text)  # Промпт для проверки качества выравнивания
    correction_prompt = Column(Text)  # Промпт для исправления ошибок выравнивания

    # Настройки LLM
    default_model_id = Column(Integer, ForeignKey('ai_models.id'), nullable=True)  # Модель по умолчанию
    temperature = Column(Float, default=0.3)  # Низкая температура для точности
    max_tokens = Column(Integer, default=8000)

    # Настройки выравнивания
    alignment_mode = Column(String(50), default='sentence')  # sentence, paragraph, semantic_block
    output_format = Column(String(50), default='json')  # json, markdown, xml

    # Опции обработки
    include_confidence = Column(Boolean, default=True)  # Включать оценку уверенности
    include_text_type = Column(Boolean, default=True)  # Определять тип текста (dialogue, description, etc.)
    include_context = Column(Boolean, default=False)  # Включать контекст из соседних глав

    # Метаданные
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    novels = relationship('Novel', back_populates='bilingual_template')
    default_model = relationship('AIModel', foreign_keys=[default_model_id])

    def __repr__(self):
        return f'<BilingualPromptTemplate {self.name}>'

    @classmethod
    def get_default_template(cls):
        """Получение шаблона по умолчанию"""
        return cls.query.filter_by(is_default=True, is_active=True).first()

    @classmethod
    def get_templates_by_category(cls, category):
        """Получение шаблонов по категории"""
        return cls.query.filter_by(category=category, is_active=True).all()

    def copy(self, new_name=None):
        """
        Создание копии шаблона для кастомизации

        Args:
            new_name: Название новой копии (если None - добавляется " (копия)")

        Returns:
            BilingualPromptTemplate: Новый объект шаблона
        """
        if not new_name:
            new_name = f"{self.name} (копия)"

        new_template = BilingualPromptTemplate(
            name=new_name,
            description=self.description,
            category=self.category,
            alignment_prompt=self.alignment_prompt,
            system_prompt=self.system_prompt,
            validation_prompt=self.validation_prompt,
            correction_prompt=self.correction_prompt,
            default_model_id=self.default_model_id,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            alignment_mode=self.alignment_mode,
            output_format=self.output_format,
            include_confidence=self.include_confidence,
            include_text_type=self.include_text_type,
            include_context=self.include_context,
            is_default=False,
            is_active=True
        )

        return new_template

    def to_dict(self):
        """Конвертация в словарь для API"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'alignment_prompt': self.alignment_prompt,
            'system_prompt': self.system_prompt,
            'validation_prompt': self.validation_prompt,
            'correction_prompt': self.correction_prompt,
            'default_model_id': self.default_model_id,
            'default_model_name': self.default_model.name if self.default_model else None,
            'default_model_provider': self.default_model.provider if self.default_model else None,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'alignment_mode': self.alignment_mode,
            'output_format': self.output_format,
            'include_confidence': self.include_confidence,
            'include_text_type': self.include_text_type,
            'include_context': self.include_context,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
