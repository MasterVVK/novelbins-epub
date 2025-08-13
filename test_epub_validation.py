#!/usr/bin/env python3
"""
Тест проверки URL/путей для EPUB источников
"""

import sys
import os
sys.path.append('/home/user/novelbins-epub/web_app')

from app.services.parser_integration import ParserIntegrationService
from parsers.parser_factory import ParserFactory

def test_epub_validation():
    """Тест проверки EPUB путей"""
    
    print("🧪 ТЕСТ ПРОВЕРКИ EPUB ПУТЕЙ")
    print("=" * 50)
    
    # Тестовые пути
    test_paths = [
        # Валидные EPUB пути
        "/home/user/novelbins-epub/web_app/instance/epub_files/qinkan.net.epub",
        "/path/to/book.epub",
        "book.epub",  
        "/epub_files/novel.epub",
        "/home/user/epub_files/test.epub/",
        
        # Невалидные пути
        "/home/user/document.pdf",
        "https://qidian.com/book/123",
        "/home/user/text.txt",
        "",
        
        # Граничные случаи
        "/home/user/book.epub.backup",
        "/home/user/.epub",
        "/epub_files/",
    ]
    
    print("📝 Тестируем валидацию путей:")
    print()
    
    for path in test_paths:
        print(f"Путь: '{path}'")
        
        # Тест детекции источника
        detected = ParserIntegrationService.detect_source_from_url(path)
        print(f"  🔍 Определенный источник: {detected}")
        
        # Тест валидации для EPUB
        is_valid_epub = ParserIntegrationService.validate_url_for_source(path, 'epub')
        print(f"  ✅ Валидный EPUB путь: {is_valid_epub}")
        
        # Тест валидации для других источников
        is_valid_qidian = ParserIntegrationService.validate_url_for_source(path, 'qidian')
        print(f"  🌐 Валидный Qidian URL: {is_valid_qidian}")
        
        print()
    
    print("🎯 ТЕСТ СПЕЦИАЛЬНЫХ СЛУЧАЕВ")
    print("=" * 50)
    
    # Реальный путь к EPUB файлу в системе
    real_epub_path = "/home/user/novelbins-epub/web_app/instance/epub_files/qinkan.net.epub"
    
    print(f"Реальный EPUB файл: {real_epub_path}")
    print(f"  Существует: {os.path.exists(real_epub_path)}")
    print(f"  Определенный источник: {ParserIntegrationService.detect_source_from_url(real_epub_path)}")
    print(f"  Валидация как EPUB: {ParserIntegrationService.validate_url_for_source(real_epub_path, 'epub')}")
    
    # Тест ParserFactory напрямую
    print(f"  ParserFactory детекция: {ParserFactory.detect_source_from_url(real_epub_path)}")
    
    print()
    print("✅ Тест завершен!")

if __name__ == "__main__":
    test_epub_validation()