"""
Сервис для извлечения глоссария из переведенных глав
"""
import re
from typing import Dict, List, Tuple, Optional
from collections import Counter
from difflib import SequenceMatcher

from app import db
from app.models import Chapter, Translation, GlossaryItem, Novel
from app.services.glossary_service import GlossaryService
from app.services.translator_service import TranslatorService


class GlossaryExtractor:
    """Извлечение глоссария из существующих переводов"""
    
    def __init__(self, novel_id: int):
        self.novel_id = novel_id
        self.novel = Novel.query.get(novel_id)
        self.existing_glossary = GlossaryItem.get_glossary_dict(novel_id)
        
    def extract_from_all_chapters(self, min_frequency: int = 2) -> Dict:
        """
        Извлечь термины из всех переведенных глав
        
        Args:
            min_frequency: Минимальная частота появления термина
        """
        print(f"📚 Начинаем извлечение глоссария для романа {self.novel.title}")
        
        # Собираем все переводы
        chapters = Chapter.query.filter_by(novel_id=self.novel_id).all()
        all_terms = Counter()
        chapter_terms = {}
        
        for chapter in chapters:
            # Получаем оригинал и перевод
            translation = Translation.query.filter_by(
                chapter_id=chapter.id,
                translation_type='initial'
            ).first()
            
            if not translation:
                continue
                
            # Извлекаем термины из главы
            terms = self.extract_from_chapter(
                chapter.original_text,
                translation.translated_text,
                chapter.chapter_number
            )
            
            chapter_terms[chapter.chapter_number] = terms
            
            # Подсчитываем частоту
            for category in terms:
                for term in terms[category]:
                    all_terms[term] += 1
        
        # Фильтруем по частоте и создаем финальный глоссарий
        filtered_glossary = self._filter_by_frequency(chapter_terms, all_terms, min_frequency)
        
        print(f"✅ Извлечено терминов: {sum(len(terms) for terms in filtered_glossary.values())}")
        return filtered_glossary
    
    def extract_from_chapter(self, original: str, translated: str, chapter_num: int) -> Dict:
        """
        Извлечь термины из одной главы
        """
        terms = {
            'characters': {},
            'locations': {},
            'terms': {},
            'techniques': {},
            'artifacts': {}
        }
        
        # 1. Извлекаем имена персонажей (заглавные буквы в русском тексте)
        characters = self._extract_proper_names(translated)
        for char in characters:
            # Пытаемся найти соответствие в оригинале
            orig_char = self._find_original_match(char, original, translated)
            if orig_char:
                terms['characters'][orig_char] = char
        
        # 2. Извлекаем специфические термины (повторяющиеся необычные слова)
        specific_terms = self._extract_specific_terms(translated)
        for term in specific_terms:
            orig_term = self._find_original_match(term, original, translated)
            if orig_term:
                category = self._categorize_term(term)
                terms[category][orig_term] = term
        
        return terms
    
    def _extract_proper_names(self, text: str) -> List[str]:
        """Извлечь имена собственные из текста"""
        names = []
        
        # Паттерн для имен (слова с заглавной буквы, исключая начало предложений)
        words = text.split()
        for i, word in enumerate(words):
            if len(word) > 1 and word[0].isupper():
                # Проверяем, что это не начало предложения
                if i > 0 and not words[i-1].endswith(('.', '!', '?')):
                    # Фильтруем общие слова
                    if word not in ['Он', 'Она', 'Это', 'Его', 'Её', 'Им', 'Их']:
                        names.append(word)
        
        # Уникальные имена с частотой > 1
        name_counts = Counter(names)
        return [name for name, count in name_counts.items() if count > 1]
    
    def _extract_specific_terms(self, text: str) -> List[str]:
        """Извлечь специфические термины"""
        terms = []
        
        # Ищем слова, характерные для жанра
        cultivation_patterns = [
            r'культивац\w*', r'ци\b', r'дао\b', r'меридиан\w*',
            r'пилюл\w*', r'артефакт\w*', r'техник\w*', r'печат\w*',
            r'формирован\w*', r'прорыв\w*', r'трибулац\w*'
        ]
        
        for pattern in cultivation_patterns:
            matches = re.findall(pattern, text.lower())
            terms.extend(matches)
        
        # Ищем составные термины
        compound_patterns = [
            r'[А-Я][а-я]+\s+[А-Я][а-я]+',  # Два слова с заглавных
            r'[а-я]+\s+[а-я]+ци\w*',  # что-то с "ци"
            r'[а-я]+\s+дао',  # что-то с "дао"
        ]
        
        for pattern in compound_patterns:
            matches = re.findall(pattern, text)
            terms.extend(matches)
        
        return list(set(terms))
    
    def _find_original_match(self, russian_term: str, original: str, translated: str) -> Optional[str]:
        """
        Найти соответствие в оригинальном тексте
        Упрощенный метод - можно улучшить с помощью ML
        """
        # Находим позицию термина в переводе
        pos = translated.find(russian_term)
        if pos == -1:
            return None
        
        # Оцениваем относительную позицию (0-1)
        relative_pos = pos / len(translated)
        
        # Ищем в оригинале в похожей позиции
        search_start = int(len(original) * max(0, relative_pos - 0.1))
        search_end = int(len(original) * min(1, relative_pos + 0.1))
        search_window = original[search_start:search_end]
        
        # Извлекаем китайские термины из окна
        chinese_terms = re.findall(r'[\u4e00-\u9fff]+', search_window)
        
        # Возвращаем наиболее вероятный (самый длинный уникальный)
        if chinese_terms:
            term_counts = Counter(chinese_terms)
            # Предпочитаем термины длиной 2-4 иероглифа
            good_terms = [t for t in term_counts if 2 <= len(t) <= 4]
            if good_terms:
                return max(good_terms, key=lambda t: term_counts[t])
        
        return None
    
    def _categorize_term(self, term: str) -> str:
        """Определить категорию термина"""
        term_lower = term.lower()
        
        if any(word in term_lower for word in ['гора', 'долина', 'город', 'деревня', 'пещера', 'дворец']):
            return 'locations'
        elif any(word in term_lower for word in ['техника', 'искусство', 'метод', 'стиль']):
            return 'techniques'
        elif any(word in term_lower for word in ['меч', 'печать', 'пилюля', 'сокровище']):
            return 'artifacts'
        else:
            return 'terms'
    
    def _filter_by_frequency(self, chapter_terms: Dict, all_terms: Counter, min_freq: int) -> Dict:
        """Фильтровать термины по частоте появления"""
        filtered = {'characters': {}, 'locations': {}, 'terms': {}, 'techniques': {}, 'artifacts': {}}
        
        for chapter_num, terms in chapter_terms.items():
            for category in terms:
                for orig, trans in terms[category].items():
                    key = (orig, trans)
                    if all_terms[key] >= min_freq:
                        filtered[category][orig] = trans
        
        return filtered
    
    def save_to_database(self, extracted_glossary: Dict) -> int:
        """Сохранить извлеченный глоссарий в БД"""
        saved_count = 0
        
        for category, terms in extracted_glossary.items():
            for original, translation in terms.items():
                # Проверяем, нет ли уже такого термина
                existing = GlossaryItem.query.filter_by(
                    novel_id=self.novel_id,
                    english_term=original,
                    is_active=True
                ).first()
                
                if not existing:
                    item = GlossaryItem(
                        novel_id=self.novel_id,
                        english_term=original,
                        russian_term=translation,
                        category=category,
                        is_auto_generated=True,
                        is_active=True
                    )
                    db.session.add(item)
                    saved_count += 1
        
        db.session.commit()
        print(f"💾 Сохранено {saved_count} новых терминов в глоссарий")
        return saved_count


class GlossaryCopier:
    """Копирование глоссария между книгами"""
    
    @staticmethod
    def copy_glossary(source_novel_id: int, target_novel_id: int, 
                     categories: List[str] = None, theme_filter: str = None) -> int:
        """
        Копировать глоссарий из одной книги в другую
        
        Args:
            source_novel_id: ID книги-источника
            target_novel_id: ID целевой книги
            categories: Список категорий для копирования (если None - все)
            theme_filter: Фильтр по тематике (например, 'ballistics')
        """
        copied_count = 0
        
        # Получаем термины из источника
        query = GlossaryItem.query.filter_by(
            novel_id=source_novel_id,
            is_active=True
        )
        
        if categories:
            query = query.filter(GlossaryItem.category.in_(categories))
        
        source_items = query.all()
        
        for item in source_items:
            # Применяем тематический фильтр
            if theme_filter and not GlossaryCopier._matches_theme(item, theme_filter):
                continue
            
            # Проверяем, нет ли уже такого термина в целевой книге
            existing = GlossaryItem.query.filter_by(
                novel_id=target_novel_id,
                english_term=item.english_term,
                is_active=True
            ).first()
            
            if not existing:
                # Создаем копию
                new_item = GlossaryItem(
                    novel_id=target_novel_id,
                    english_term=item.english_term,
                    russian_term=item.russian_term,
                    category=item.category,
                    description=item.description,
                    is_auto_generated=True,
                    is_active=True
                )
                db.session.add(new_item)
                copied_count += 1
        
        db.session.commit()
        return copied_count
    
    @staticmethod
    def _matches_theme(item: GlossaryItem, theme: str) -> bool:
        """Проверить соответствие термина тематике"""
        theme_keywords = {
            'ballistics': ['пуля', 'выстрел', 'калибр', 'траектория', 'винтовка', 'патрон'],
            'cultivation': ['культивация', 'ци', 'дао', 'меридиан', 'прорыв'],
            'military': ['солдат', 'армия', 'генерал', 'битва', 'война'],
            'medicine': ['лекарство', 'пилюля', 'врач', 'лечение', 'болезнь']
        }
        
        keywords = theme_keywords.get(theme, [])
        term_text = f"{item.english_term} {item.russian_term} {item.description or ''}".lower()
        
        return any(kw in term_text for kw in keywords)
    
    @staticmethod
    def merge_glossaries(novel_id: int, source_glossaries: List[int]) -> int:
        """
        Объединить несколько глоссариев в один
        
        Args:
            novel_id: ID целевой книги
            source_glossaries: Список ID книг-источников
        """
        merged_count = 0
        
        for source_id in source_glossaries:
            count = GlossaryCopier.copy_glossary(source_id, novel_id)
            merged_count += count
        
        return merged_count