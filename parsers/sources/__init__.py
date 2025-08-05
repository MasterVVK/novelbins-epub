"""
Конкретные реализации парсеров для различных источников
"""

from .qidian_parser import QidianParser
from .epub_parser import EPUBParser

__all__ = ['QidianParser', 'EPUBParser']