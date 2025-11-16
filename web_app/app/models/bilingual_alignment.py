"""
Модель для хранения результатов двуязычного выравнивания
"""
from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, Text, JSON, Float, Boolean, DateTime, String
from sqlalchemy.orm import relationship
from app import db


class BilingualAlignment(db.Model):
    """
    Кэш результатов LLM-выравнивания китайского оригинала и русского перевода.
    Сохраняется один раз, используется при каждой генерации EPUB.
    """
    __tablename__ = 'bilingual_alignments'

    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=False, unique=True)

    # Результат выравнивания в JSON формате
    alignment_data = Column(JSON, nullable=False)
    # Формат:
    # {
    #   "alignments": [
    #     {
    #       "ru": "Русское предложение 1",
    #       "zh": "中文句子1",
    #       "type": "dialogue",  # dialogue, description, action, internal, etc.
    #       "confidence": 0.95
    #     },
    #     ...
    #   ],
    #   "stats": {
    #     "total_pairs": 42,
    #     "ru_sentences": 45,
    #     "zh_sentences": 42,
    #     "avg_confidence": 0.93
    #   }
    # }

    # Метаданные создания
    alignment_method = Column(String(50), default='llm')  # 'llm', 'regex', 'manual'
    model_used = Column(String(100))  # Название LLM модели (например, "gemini-2.0-flash")
    template_used_id = Column(Integer, ForeignKey('bilingual_prompt_templates.id'))  # Какой шаблон использовался

    # Оценка качества
    quality_score = Column(Float)  # 0.0 - 1.0 (автоматическая оценка)
    coverage_ru = Column(Float)  # Процент покрытия русского текста
    coverage_zh = Column(Float)  # Процент покрытия китайского текста
    avg_confidence = Column(Float)  # Средняя уверенность LLM

    # Статистика
    total_pairs = Column(Integer)  # Всего пар
    misalignment_count = Column(Integer, default=0)  # Количество пар с низкой уверенностью (<0.7)

    # Ручная верификация
    verified_by_human = Column(Boolean, default=False)
    verification_notes = Column(Text)
    verified_at = Column(DateTime)

    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    chapter = relationship('Chapter', back_populates='bilingual_alignment')
    template_used = relationship('BilingualPromptTemplate')

    def __repr__(self):
        return f'<BilingualAlignment chapter_id={self.chapter_id}, pairs={self.total_pairs}, quality={self.quality_score:.2f}>'

    def to_dict(self):
        """Конвертация в словарь для API"""
        return {
            'id': self.id,
            'chapter_id': self.chapter_id,
            'alignment_data': self.alignment_data,
            'alignment_method': self.alignment_method,
            'model_used': self.model_used,
            'template_used_id': self.template_used_id,
            'quality_score': self.quality_score,
            'coverage_ru': self.coverage_ru,
            'coverage_zh': self.coverage_zh,
            'avg_confidence': self.avg_confidence,
            'total_pairs': self.total_pairs,
            'misalignment_count': self.misalignment_count,
            'verified_by_human': self.verified_by_human,
            'verification_notes': self.verification_notes,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @property
    def is_high_quality(self):
        """Проверка высокого качества выравнивания"""
        return (
            self.quality_score and self.quality_score > 0.8 and
            self.coverage_ru and self.coverage_ru > 0.85 and
            self.coverage_zh and self.coverage_zh > 0.85 and
            self.avg_confidence and self.avg_confidence > 0.75
        )

    @property
    def needs_review(self):
        """Требуется ли ручная проверка"""
        return (
            not self.verified_by_human and (
                self.quality_score < 0.7 or
                self.misalignment_count > (self.total_pairs * 0.2)  # Больше 20% с низкой уверенностью
            )
        )
