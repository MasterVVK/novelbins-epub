#!/usr/bin/env python3
"""
Пример использования шаблона для перевода "我欲封天" (I Shall Seal the Heavens)
Демонстрирует, как применить новый шаблон к EPUB файлу
"""

import sys
import os
import json
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from translation_templates.issth_template import ISSTH_TEMPLATE_CONFIG, ISSTH_TRANSLATION_PROMPT
from parsers.sources.epub_parser import EPUBParser

def demonstrate_issth_template():
    """Демонстрация использования шаблона для ISSTH"""
    
    print("=" * 80)
    print("ДЕМОНСТРАЦИЯ ШАБЛОНА: Я ХОЧУ ЗАПЕЧАТАТЬ НЕБЕСА")
    print("=" * 80)
    
    # Информация о шаблоне
    config = ISSTH_TEMPLATE_CONFIG
    print(f"📚 Название: {config['name']}")
    print(f"🔤 Оригинал: {config['original_title']}")
    print(f"🇬🇧 English: {config['english_title']}")
    print(f"🇷🇺 Русский: {config['russian_title']}")
    print(f"✍️ Автор: {config['author']}")
    print(f"📂 Категория: {config['category']}")
    print(f"👤 Главный герой: {config['main_character']}")
    print(f"🌍 Сеттинг: {config['setting']}")
    
    print("\n🎯 Уникальные элементы:")
    for element in config['unique_elements']:
        print(f"  • {element}")
    
    print("\n" + "=" * 80)
    print("КОНФИГУРАЦИЯ ДЛЯ СИСТЕМЫ ПЕРЕВОДА")
    print("=" * 80)
    
    # Параметры для AI
    print(f"🌡️ Температура: {config['temperature']}")
    print(f"📏 Максимум токенов: {config['max_tokens']}")
    
    # Путь к EPUB файлу
    epub_path = "/home/user/novelbins-epub/web_app/instance/epub_files/qinkan.net.epub"
    
    if os.path.exists(epub_path):
        print(f"\n📖 EPUB файл найден: {epub_path}")
        
        # Демонстрация парсинга с новым шаблоном
        print("\n" + "-" * 60)
        print("ДЕМОНСТРАЦИЯ ПАРСИНГА ПЕРВЫХ 3 ГЛАВ")
        print("-" * 60)
        
        try:
            # Создаем парсер с ограничением в 3 главы для демонстрации
            parser = EPUBParser(epub_path=epub_path, max_chapters=3)
            
            if parser.load_epub(epub_path):
                book_info = parser.get_book_info()
                chapters = parser.get_chapter_list()
                
                print(f"📚 Информация о книге:")
                print(f"  Название: {book_info.get('title', 'Не определено')}")
                print(f"  Автор: {book_info.get('author', 'Не определен')}")
                print(f"  Всего глав в файле: {book_info.get('total_chapters', 0)}")
                print(f"  Извлечено для демонстрации: {len(chapters)}")
                
                print(f"\n📑 Первые {len(chapters)} глав:")
                for i, chapter in enumerate(chapters, 1):
                    title = chapter.get('title', f"Глава {chapter.get('number')}")
                    print(f"  {i}. {title} (~{chapter.get('word_count', 0)} слов)")
                
                # Показываем начало первой главы
                if chapters:
                    first_chapter = parser.get_chapter_content(chapters[0]['chapter_id'])
                    content_preview = first_chapter['content'][:300] + "..." if len(first_chapter['content']) > 300 else first_chapter['content']
                    
                    print(f"\n📄 Предварительный просмотр первой главы:")
                    print(f"📝 Название: {first_chapter['title']}")
                    print(f"📊 Количество слов: {first_chapter['word_count']}")
                    print(f"📖 Начало содержимого:")
                    print("-" * 40)
                    print(content_preview)
                    print("-" * 40)
                
            else:
                print("❌ Не удалось загрузить EPUB файл")
                
        except Exception as e:
            print(f"❌ Ошибка при демонстрации парсинга: {e}")
    else:
        print(f"\n❌ EPUB файл не найден: {epub_path}")
        print("   Убедитесь, что файл существует для полной демонстрации")
    
    print("\n" + "=" * 80)
    print("ПРИМЕР ПРОМПТА ДЛЯ ПЕРЕВОДА")
    print("=" * 80)
    
    # Показываем сокращенную версию промпта
    prompt_lines = ISSTH_TRANSLATION_PROMPT.split('\n')[:30]  # Первые 30 строк
    print('\n'.join(prompt_lines))
    print("...")
    print("[Промпт сокращен для демонстрации]")
    
    print("\n" + "=" * 80)
    print("ИНСТРУКЦИИ ПО ИСПОЛЬЗОВАНИЮ")
    print("=" * 80)
    
    instructions = """
    1. 📁 Загрузите EPUB файл "我欲封天" в систему
    2. 🎯 Выберите шаблон "Сянься (Я хочу запечатать небеса)"
    3. ⚙️ Настройте параметры:
       • Температура: 0.1 (для точности)
       • Максимум токенов: 24000
       • Максимум глав: по желанию
    4. 🚀 Запустите процесс перевода
    5. ✏️ Используйте встроенный редактор для доработки
    6. 📚 Генерируйте финальный EPUB
    
    🎯 Ключевые особенности шаблона:
    • Специализирован для стиля автора Ergen
    • Учитывает философскую глубину произведения
    • Правильно переводит алхимическую терминологию
    • Сохраняет эмоциональную окраску оригинала
    • Корректно обрабатывает уникальные концепции романа
    """
    
    print(instructions)
    
    print("\n" + "=" * 80)
    print("ЗАВЕРШЕНИЕ ДЕМОНСТРАЦИИ")
    print("=" * 80)

def load_glossary():
    """Загрузка глоссария для демонстрации"""
    glossary_path = Path(__file__).parent / "issth_glossary.json"
    
    if glossary_path.exists():
        with open(glossary_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print(f"⚠️ Глоссарий не найден: {glossary_path}")
        return {}

def show_glossary_sample():
    """Показать примеры из глоссария"""
    print("\n" + "=" * 80)
    print("ОБРАЗЦЫ ИЗ ГЛОССАРИЯ")
    print("=" * 80)
    
    glossary = load_glossary()
    
    if glossary:
        # Показываем основных персонажей
        print("👥 Основные персонажи:")
        for chinese, russian in glossary.get('main_characters', {}).items():
            print(f"   {chinese} → {russian}")
        
        # Показываем ключевые локации
        print("\n🏔️ Ключевые локации:")
        for chinese, russian in list(glossary.get('locations', {}).items())[:5]:
            print(f"   {chinese} → {russian}")
        
        # Показываем уровни культивации
        print("\n⚡ Уровни культивации:")
        for chinese, russian in list(glossary.get('cultivation_levels', {}).items())[:5]:
            print(f"   {chinese} → {russian}")
            
        # Показываем уникальные термины ISSTH
        print("\n🔮 Уникальные термины ISSTH:")
        for chinese, russian in glossary.get('unique_issth_terms', {}).items():
            print(f"   {chinese} → {russian}")

if __name__ == "__main__":
    demonstrate_issth_template()
    show_glossary_sample()