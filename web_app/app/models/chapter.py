from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from app import db


class Chapter(db.Model):
    """Модель главы"""
    __tablename__ = 'chapters'

    id = Column(Integer, primary_key=True)
    novel_id = Column(Integer, ForeignKey('novels.id'), nullable=False)
    chapter_number = Column(Integer, nullable=False)

    # Оригинальный контент
    original_title = Column(String(500))
    original_text = Column(Text)
    url = Column(String(500))

    # Статистика
    word_count_original = Column(Integer, default=0)
    word_count_translated = Column(Integer, default=0)
    paragraph_count = Column(Integer, default=0)

    # Статус
    status = Column(String(50), default='pending')  # pending, parsed, translated, edited, error

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    novel = relationship('Novel', back_populates='chapters')
    translations = relationship('Translation', back_populates='chapter', cascade='all, delete-orphan', order_by='Translation.id')
    prompt_history = relationship('PromptHistory', back_populates='chapter', cascade='all, delete-orphan')
    bilingual_alignment = relationship('BilingualAlignment', back_populates='chapter', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Chapter {self.chapter_number} of {self.novel.title}>'

    @property
    def current_translation(self):
        """Текущий перевод (исходный, не отредактированный)"""
        # Ищем последний перевод, который НЕ является редактурой
        for trans in reversed(self.translations):
            if trans.translation_type != 'edited':
                return trans
        return None

    @property
    def edited_translation(self):
        """Отредактированная версия"""
        edited_translations = [t for t in self.translations if t.translation_type == 'edited']
        return edited_translations[-1] if edited_translations else None

    @property
    def is_translated(self):
        """Проверка наличия перевода"""
        return self.status in ['translated', 'edited', 'aligned']

    @property
    def is_edited(self):
        """Проверка наличия редактуры"""
        return self.status == 'edited'

    @property
    def translated_title(self):
        """Переведённое название главы

        Возвращает название из наиболее актуальной версии перевода:
        - Приоритет 1: Последний перевод с валидным translated_title (среди всех)
        - Приоритет 2: None (если названия нет ни в одном переводе)
        """
        def is_valid_title(title):
            """Проверяет, является ли строка валидным названием главы"""
            if not title:
                return False
            title_lower = title.lower().strip()
            # Валидные префиксы для названий
            valid_prefixes = ('глава', 'chapter', '**глава', 'пролог', 'эпилог', 'интерлюдия')
            # Если название слишком длинное и не начинается с валидного префикса — это скорее всего текст
            if len(title) > 80 and not title_lower.startswith(valid_prefixes):
                return False
            return True

        # Ищем среди всех переводов (от новых к старым по ID) первый с валидным названием
        sorted_translations = sorted(self.translations, key=lambda t: t.id, reverse=True)
        for trans in sorted_translations:
            if is_valid_title(trans.translated_title):
                return trans.translated_title
        return None 