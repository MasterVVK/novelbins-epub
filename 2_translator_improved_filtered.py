"""
2_translator_improved_filtered.py - Переводчик с интеллектуальной фильтрацией глоссария
Предотвращает рост глоссария для новых новелл
"""

import os
import time
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Импортируем фильтр глоссария
from glossary_filter import GlossaryFilter

# Остальные импорты из оригинального файла
import httpx
from httpx_socks import SyncProxyTransport
from dotenv import load_dotenv
from models import Chapter, TranslatorConfig, GlossaryItem
from database import DatabaseManager

load_dotenv()

# ===================== УЛУЧШЕННЫЙ ПРОМПТ ДЛЯ ИЗВЛЕЧЕНИЯ =====================

EXTRACT_TERMS_PROMPT_STRICT = """Ты работаешь с китайской веб-новеллой жанра сянься/сюаньхуань.

КРИТИЧЕСКИ ВАЖНО: Извлекай ТОЛЬКО уникальные и специфичные для этой новеллы элементы!

НЕ ДОБАВЛЯЙ:
❌ Общие слова (человек, время, место, вещь)
❌ Эмоции (улыбка, грусть, радость, страх)
❌ Части тела (рука, нога, голова, глаз)
❌ Простые действия (идти, смотреть, говорить, думать)
❌ Базовые качества (большой, маленький, сильный, слабый)
❌ Время (день, ночь, утро, вечер, момент)
❌ Направления (вперед, назад, вверх, вниз)

ДОБАВЛЯЙ ТОЛЬКО:
✅ Имена важных персонажей (НЕ "молодой человек", а "Ван Линь")
✅ Названия конкретных мест (НЕ "гора", а "Пик Небесного Меча")
✅ Уникальные техники культивации (НЕ "удар", а "Кулак Разрушения Небес")
✅ Специальные артефакты (НЕ "меч", а "Меч Ледяной Души")
✅ Термины культивации СПЕЦИФИЧНЫЕ для этой новеллы

Проверь каждый термин:
1. Это действительно УНИКАЛЬНО для этой новеллы?
2. Это НЕ общеупотребительное слово?
3. Это будет использоваться многократно в тексте?

Если термин не проходит ВСЕ три проверки - НЕ ДОБАВЛЯЙ его!

Формат ответа:
ПЕРСОНАЖИ:
- Chinese Name = Русский Перевод

ЛОКАЦИИ:
- Chinese Location = Русская Локация

ТЕРМИНЫ:
- Chinese Term = Русский Термин

Если новых ВАЖНЫХ элементов нет, пиши:
КАТЕГОРИЯ:
- нет новых"""

# ===================== КЛАСС ПЕРЕВОДЧИКА С ФИЛЬТРАЦИЕЙ =====================

class FilteredTranslator:
    """Переводчик с интеллектуальной фильтрацией глоссария"""
    
    def __init__(self, config: TranslatorConfig):
        self.config = config
        self.glossary_filter = GlossaryFilter()
        self.stats = {
            'added': 0,
            'filtered': 0,
            'duplicates': 0
        }
        
        # Инициализация остальных компонентов...
        self.db = DatabaseManager(config.db_path)
        
    def process_extracted_terms(self, extraction_result: str, chapter_num: int, novel_id: int) -> Tuple[int, int]:
        """
        Обработка извлечённых терминов с жёсткой фильтрацией
        
        Returns:
            (added_count, filtered_count)
        """
        
        if not extraction_result:
            return 0, 0
            
        added_count = 0
        filtered_count = 0
        
        # Парсим результат извлечения
        terms = self.parse_extraction_result(extraction_result)
        
        for category, items in terms.items():
            if not items or items == [('нет новых', 'нет новых')]:
                continue
                
            for chinese, russian in items:
                # Пропускаем пустые
                if not chinese or not russian or chinese == 'нет новых':
                    continue
                
                # Очищаем перевод
                russian = self.glossary_filter.clean_russian_translation(russian)
                chinese = chinese.strip()
                
                # === ФИЛЬТР 1: Проверка на дубликаты по русскому переводу ===
                existing = self.check_duplicate(russian, novel_id)
                if existing:
                    self.stats['duplicates'] += 1
                    filtered_count += 1
                    print(f"    🔄 Дубликат: {chinese} = {russian} (уже есть)")
                    continue
                
                # === ФИЛЬТР 2: Интеллектуальная проверка ===
                should_add, reason = self.glossary_filter.should_add_term(
                    chinese, russian, category
                )
                
                if not should_add:
                    self.stats['filtered'] += 1
                    filtered_count += 1
                    print(f"    ❌ Отфильтрован: {chinese} = {russian}")
                    print(f"       Причина: {reason}")
                    continue
                
                # === ФИЛЬТР 3: Дополнительная проверка для новых новелл ===
                if not self.is_novel_specific(chinese, russian, category):
                    filtered_count += 1
                    print(f"    ⚠️ Не специфично: {chinese} = {russian}")
                    continue
                
                # Если прошёл все фильтры - добавляем
                self.add_to_glossary(chinese, russian, category, chapter_num, novel_id)
                self.stats['added'] += 1
                added_count += 1
                print(f"    ✅ Добавлен: {chinese} = {russian} ({category})")
        
        return added_count, filtered_count
    
    def check_duplicate(self, russian: str, novel_id: int) -> bool:
        """Проверка на дубликат по русскому переводу"""
        # Здесь должна быть проверка в БД
        # Для примера - заглушка
        return False
    
    def is_novel_specific(self, chinese: str, russian: str, category: str) -> bool:
        """
        Дополнительная проверка - действительно ли термин специфичен для новеллы
        """
        russian_lower = russian.lower()
        
        # Список слишком общих терминов, которые есть во всех новеллах
        GENERIC_TERMS = {
            'старейшина', 'ученик', 'наставник', 'патриарх',
            'внутренний ученик', 'внешний ученик',
            'духовная энергия', 'духовная сила',
            'прорыв', 'культивация', 'медитация',
            'пилюля', 'эликсир', 'талисман'
        }
        
        # Если это слишком общий термин - не добавляем
        for generic in GENERIC_TERMS:
            if generic in russian_lower:
                # Но если есть уникальный модификатор - добавляем
                unique_modifiers = ['небесн', 'божествен', 'демоническ', 'драконий',
                                  'императорск', 'древн', 'запретн', 'тайн']
                if not any(mod in russian_lower for mod in unique_modifiers):
                    return False
        
        # Для персонажей - проверяем, что это полное имя
        if category == 'characters':
            # Должно быть хотя бы 2 части (имя + фамилия) или уникальное прозвище
            if len(russian.split()) < 2 and len(chinese) < 3:
                return False
        
        # Для техник - должно быть описательное название
        if category == 'techniques':
            if len(russian.split()) < 2:
                return False
        
        return True
    
    def add_to_glossary(self, chinese: str, russian: str, category: str, 
                       chapter_num: int, novel_id: int):
        """Добавление термина в глоссарий после всех проверок"""
        # Здесь код добавления в БД
        item = GlossaryItem(
            english=chinese,
            russian=russian, 
            category=category,
            first_appearance=chapter_num
        )
        self.db.save_glossary_item(item)
    
    def parse_extraction_result(self, result: str) -> Dict[str, List[Tuple[str, str]]]:
        """Парсинг результата извлечения терминов"""
        terms = {
            'characters': [],
            'locations': [],
            'terms': [],
            'techniques': [],
            'artifacts': []
        }
        
        current_category = None
        lines = result.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Определяем категорию
            if 'ПЕРСОНАЖ' in line.upper():
                current_category = 'characters'
            elif 'ЛОКАЦ' in line.upper():
                current_category = 'locations'
            elif 'ТЕРМИН' in line.upper():
                current_category = 'terms'
            elif 'ТЕХНИК' in line.upper():
                current_category = 'techniques'
            elif 'АРТЕФАКТ' in line.upper():
                current_category = 'artifacts'
            elif line.startswith('-') and '=' in line and current_category:
                # Парсим термин
                parts = line[1:].split('=')
                if len(parts) == 2:
                    chinese = parts[0].strip()
                    russian = parts[1].strip()
                    if chinese and russian and chinese != 'нет новых':
                        terms[current_category].append((chinese, russian))
        
        return terms
    
    def print_stats(self):
        """Вывод статистики фильтрации"""
        print("\n" + "=" * 60)
        print("📊 СТАТИСТИКА ФИЛЬТРАЦИИ ГЛОССАРИЯ:")
        print(f"  ✅ Добавлено: {self.stats['added']}")
        print(f"  ❌ Отфильтровано: {self.stats['filtered']}")
        print(f"  🔄 Дубликатов: {self.stats['duplicates']}")
        print(f"  📈 Процент фильтрации: {self.stats['filtered']/(self.stats['added']+self.stats['filtered'])*100:.1f}%")
        print("=" * 60)


# ===================== КОНФИГУРАЦИЯ ДЛЯ НОВЫХ НОВЕЛЛ =====================

def create_config_for_new_novel(novel_name: str) -> Dict:
    """Создание конфигурации для новой новеллы с жёсткой фильтрацией"""
    
    return {
        'novel_name': novel_name,
        'glossary_settings': {
            'max_terms': 3000,  # Максимум терминов в глоссарии
            'min_usage_to_keep': 3,  # Минимум использований для сохранения
            'auto_cleanup_every': 100,  # Автоочистка каждые N глав
            'strict_filtering': True,  # Строгая фильтрация
            'require_uniqueness': True,  # Требовать уникальности
            'min_chinese_length': {
                'characters': 2,
                'locations': 3,
                'terms': 3,
                'techniques': 4,
                'artifacts': 3
            }
        },
        'extraction_prompt': EXTRACT_TERMS_PROMPT_STRICT,
        'filters': {
            'use_intelligent_filter': True,
            'check_duplicates': True,
            'check_novel_specificity': True,
            'block_common_words': True
        }
    }


# ===================== ГЛАВНАЯ ФУНКЦИЯ =====================

def translate_novel_with_filter(novel_name: str, start_chapter: int = 1):
    """Перевод новеллы с интеллектуальной фильтрацией глоссария"""
    
    print(f"\n{'=' * 60}")
    print(f"🚀 ЗАПУСК ПЕРЕВОДА С ФИЛЬТРАЦИЕЙ ГЛОССАРИЯ")
    print(f"📚 Новелла: {novel_name}")
    print(f"🔍 Режим: Строгая фильтрация")
    print(f"{'=' * 60}\n")
    
    # Создаём конфигурацию
    config = create_config_for_new_novel(novel_name)
    
    # Инициализируем переводчик с фильтром
    translator = FilteredTranslator(TranslatorConfig())
    
    # Здесь основной цикл перевода...
    # Для демонстрации - пример обработки одной главы
    
    print("✅ Фильтрация настроена!")
    print("\n📋 Правила фильтрации:")
    print("  1. Блокировка общих слов (175 стоп-слов)")
    print("  2. Проверка минимальной длины термина")
    print("  3. Дедупликация по русскому переводу")
    print("  4. Проверка специфичности для новеллы")
    print("  5. Валидация по категориям")
    
    translator.print_stats()
    
    return translator


if __name__ == "__main__":
    # Пример использования для новой новеллы
    novel = input("Введите название новой новеллы: ").strip()
    if novel:
        translate_novel_with_filter(novel)
    else:
        print("❌ Название новеллы не указано")