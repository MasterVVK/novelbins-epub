"""
models.py - Общие модели данных для всех модулей
"""
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class Chapter:
    """Модель главы"""
    number: int
    original_title: str
    original_text: str
    url: str
    word_count: int
    paragraph_count: int

    # Поля для перевода (заполняются позже)
    translated_title: Optional[str] = None
    translated_text: Optional[str] = None
    summary: Optional[str] = None
    translation_time: Optional[float] = None
    translated_at: Optional[datetime] = None


@dataclass
class GlossaryItem:
    """Элемент глоссария"""
    english: str
    russian: str
    category: str  # 'character', 'location', 'term'
    first_appearance_chapter: int
    description: str = ""


@dataclass
class TranslationContext:
    """Контекст для перевода"""
    previous_summaries: List[Dict[str, str]]  # [{'chapter': 1, 'summary': '...'}]
    glossary: Dict[str, Dict[str, str]]  # {'characters': {}, 'locations': {}, 'terms': {}}


@dataclass
class ParserConfig:
    """Конфигурация парсера"""
    base_url: str = "https://novelbins.com"
    novel_url: str = "https://novelbins.com/novel/shrouding-the-heavens-1150192/"
    max_chapters: int = 3
    min_paragraph_length: int = 50
    request_delay: float = 1.0


@dataclass
class TranslatorConfig:
    """Конфигурация переводчика"""
    api_keys: List[str]
    model_name: str = "gemini-2.5-flash-preview-05-20"
    temperature: float = 0.1
    max_output_tokens: int = 16384
    request_delay: float = 2.0
    proxy_url: Optional[str] = None


@dataclass
class EPUBConfig:
    """Конфигурация генератора EPUB"""
    book_title: str = "Покрывая Небеса"
    book_author: str = "Чэнь Дун"
    book_language: str = "ru"
    include_glossary: bool = True
    include_summaries: bool = False