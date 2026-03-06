"""
Конкретные реализации парсеров для различных источников
"""

from .qidian_parser import QidianParser
from .epub_parser import EPUBParser
from .czbooks_parser import CZBooksParser
from .ttkan_parser import TtkanParser

__all__ = ['QidianParser', 'EPUBParser', 'CZBooksParser', 'TtkanParser']