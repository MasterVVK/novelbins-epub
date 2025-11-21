from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app import db


class GlossaryItem(db.Model):
    """Модель элемента глоссария"""
    __tablename__ = 'glossary_items'

    id = Column(Integer, primary_key=True)
    novel_id = Column(Integer, ForeignKey('novels.id'), nullable=False)
    
    # Основная информация
    english_term = Column('english', String(255), nullable=False)
    russian_term = Column('russian', String(255), nullable=False)
    category = Column(String(50), nullable=False)  # character, location, term, technique, artifact
    
    # Дополнительная информация
    description = Column(Text)
    first_appearance_chapter = Column(Integer)
    usage_count = Column(Integer, default=0)
    
    # Настройки
    is_active = Column(Boolean, default=True)
    is_auto_generated = Column(Boolean, default=False)  # Автоматически извлеченный термин
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    novel = relationship('Novel', back_populates='glossary_items')
    
    def __repr__(self):
        return f'<GlossaryItem {self.english_term} → {self.russian_term}>'
    
    @classmethod
    def get_by_novel_and_category(cls, novel_id, category):
        """Получение элементов глоссария по новелле и категории"""
        return cls.query.filter_by(
            novel_id=novel_id, 
            category=category, 
            is_active=True
        ).order_by(cls.english_term).all()
    
    @classmethod
    def get_glossary_dict(cls, novel_id):
        """Получение глоссария в виде словаря для промптов"""
        items = cls.query.filter_by(novel_id=novel_id, is_active=True).all()

        glossary = {
            'characters': {},
            'locations': {},
            'terms': {},
            'techniques': {},
            'artifacts': {}
        }

        for item in items:
            if item.category in glossary:
                glossary[item.category][item.english_term] = item.russian_term

        return glossary

    @classmethod
    def get_chinese_terms_dict(cls, novel_id):
        """
        Получить словарь: китайский_термин → (русский, описание, категория)

        Примечание: В поле english_term фактически хранятся китайские иероглифы

        Returns:
            {
                "李楊": {
                    "russian": "Ли Ян",
                    "description": "...",
                    "category": "characters"
                },
                ...
            }
        """
        items = cls.query.filter_by(novel_id=novel_id, is_active=True).all()
        result = {}

        for item in items:
            if item.english_term:  # Фактически это китайский термин
                result[item.english_term] = {
                    'russian': item.russian_term,
                    'description': item.description or '',
                    'category': item.category
                }

        return result
    
    def increment_usage(self):
        """Увеличение счетчика использования"""
        self.usage_count += 1
        self.updated_at = datetime.utcnow()
    
    @classmethod
    def find_similar_terms(cls, novel_id, english_term, threshold=0.8):
        """Поиск похожих терминов"""
        from difflib import SequenceMatcher
        
        items = cls.query.filter_by(novel_id=novel_id, is_active=True).all()
        similar = []
        
        for item in items:
            similarity = SequenceMatcher(None, english_term.lower(), item.english_term.lower()).ratio()
            if similarity >= threshold:
                similar.append((item, similarity))
        
        return sorted(similar, key=lambda x: x[1], reverse=True) 