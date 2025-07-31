"""
Пакет парсеров для различных источников книг
"""

from .base.base_parser import BaseParser
from .parser_factory import ParserFactory, create_parser, create_parser_from_url, detect_source, get_available_sources

__all__ = [
    'BaseParser', 
    'ParserFactory', 
    'create_parser', 
    'create_parser_from_url', 
    'detect_source', 
    'get_available_sources'
]