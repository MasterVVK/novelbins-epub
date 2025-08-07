"""
Сервис для управления глоссарием
"""
from typing import List, Dict, Optional, Tuple
from app.models import GlossaryItem, Novel
from app import db


class GlossaryService:
    """Сервис для работы с глоссарием"""
    
    @staticmethod
    def get_glossary_for_novel(novel_id: int) -> Dict[str, List[GlossaryItem]]:
        """Получение глоссария для новеллы, сгруппированного по категориям"""
        items = GlossaryItem.query.filter_by(
            novel_id=novel_id, 
            is_active=True
        ).order_by(GlossaryItem.english_term).all()
        
        glossary = {
            'characters': [],
            'locations': [],
            'terms': [],
            'techniques': [],
            'artifacts': []
        }
        
        for item in items:
            if item.category in glossary:
                glossary[item.category].append(item)
        
        return glossary
    
    @staticmethod
    def get_glossary_dict(novel_id: int) -> Dict[str, Dict[str, str]]:
        """Получение глоссария в виде словаря для промптов"""
        return GlossaryItem.get_glossary_dict(novel_id)
    
    @staticmethod
    def add_term(novel_id: int, english_term: str, russian_term: str, 
                 category: str, description: str = "", chapter_number: int = None) -> GlossaryItem:
        """Добавление нового термина в глоссарий"""
        # Проверяем, нет ли уже такого термина
        existing = GlossaryItem.query.filter_by(
            novel_id=novel_id,
            english_term=english_term,
            is_active=True
        ).first()
        
        if existing:
            # Обновляем существующий термин
            existing.russian_term = russian_term
            existing.category = category
            existing.description = description
            if chapter_number:
                existing.first_appearance_chapter = chapter_number
            db.session.commit()
            return existing
        
        # Создаем новый термин
        glossary_item = GlossaryItem(
            novel_id=novel_id,
            english_term=english_term,
            russian_term=russian_term,
            category=category,
            description=description,
            first_appearance_chapter=chapter_number,
            is_auto_generated=False
        )
        
        db.session.add(glossary_item)
        db.session.commit()
        return glossary_item
    
    @staticmethod
    def update_term(term_id: int, data: Dict) -> Optional[GlossaryItem]:
        """Обновление термина"""
        term = GlossaryItem.query.get(term_id)
        if not term:
            return None
        
        for key, value in data.items():
            if hasattr(term, key):
                setattr(term, key, value)
        
        db.session.commit()
        return term
    
    @staticmethod
    def delete_term(term_id: int) -> bool:
        """Удаление термина (полное удаление)"""
        term = GlossaryItem.query.get(term_id)
        if not term:
            return False
        
        db.session.delete(term)
        db.session.commit()
        return True
    
    @staticmethod
    def find_similar_terms(novel_id: int, english_term: str, threshold: float = 0.8) -> List[Tuple[GlossaryItem, float]]:
        """Поиск похожих терминов"""
        return GlossaryItem.find_similar_terms(novel_id, english_term, threshold)
    
    @staticmethod
    def search_terms(novel_id: int, query: str, category: str = None) -> List[GlossaryItem]:
        """Поиск терминов по запросу"""
        filters = [
            GlossaryItem.novel_id == novel_id,
            GlossaryItem.is_active == True
        ]
        
        if category:
            filters.append(GlossaryItem.category == category)
        
        if query:
            filters.append(
                db.or_(
                    GlossaryItem.english_term.ilike(f'%{query}%'),
                    GlossaryItem.russian_term.ilike(f'%{query}%'),
                    GlossaryItem.description.ilike(f'%{query}%')
                )
            )
        
        return GlossaryItem.query.filter(*filters).order_by(GlossaryItem.english_term).all()
    
    @staticmethod
    def get_terms_by_category(novel_id: int, category: str) -> List[GlossaryItem]:
        """Получение терминов по категории"""
        return GlossaryItem.get_by_novel_and_category(novel_id, category)
    
    @staticmethod
    def get_term_statistics(novel_id: int) -> Dict[str, int]:
        """Получение статистики по глоссарию"""
        stats = {}
        
        for category in ['characters', 'locations', 'terms', 'techniques', 'artifacts']:
            count = GlossaryItem.query.filter_by(
                novel_id=novel_id,
                category=category,
                is_active=True
            ).count()
            stats[category] = count
        
        # Общая статистика
        stats['total'] = sum(stats.values())
        stats['auto_generated'] = GlossaryItem.query.filter_by(
            novel_id=novel_id,
            is_auto_generated=True,
            is_active=True
        ).count()
        stats['manual'] = stats['total'] - stats['auto_generated']
        
        return stats
    
    @staticmethod
    def import_glossary_from_dict(novel_id: int, glossary_data: Dict[str, Dict[str, str]], 
                                 chapter_number: int = None) -> int:
        """Импорт глоссария из словаря"""
        imported_count = 0
        
        for category, terms in glossary_data.items():
            for english_term, russian_term in terms.items():
                if english_term and russian_term:
                    try:
                        GlossaryService.add_term(
                            novel_id=novel_id,
                            english_term=english_term.strip(),
                            russian_term=russian_term.strip(),
                            category=category,
                            chapter_number=chapter_number
                        )
                        imported_count += 1
                    except Exception as e:
                        print(f"Ошибка импорта термина {english_term}: {e}")
        
        return imported_count
    
    @staticmethod
    def export_glossary_to_dict(novel_id: int) -> Dict[str, Dict[str, str]]:
        """Экспорт глоссария в словарь"""
        return GlossaryItem.get_glossary_dict(novel_id)
    
    @staticmethod
    def merge_glossaries(novel_id: int, other_glossary: Dict[str, Dict[str, str]]) -> int:
        """Слияние глоссариев (добавление новых терминов)"""
        merged_count = 0
        current_glossary = GlossaryItem.get_glossary_dict(novel_id)
        
        for category, terms in other_glossary.items():
            for english_term, russian_term in terms.items():
                # Проверяем, есть ли уже такой термин
                if category in current_glossary and english_term in current_glossary[category]:
                    continue
                
                try:
                    GlossaryService.add_term(
                        novel_id=novel_id,
                        english_term=english_term,
                        russian_term=russian_term,
                        category=category
                    )
                    merged_count += 1
                except Exception as e:
                    print(f"Ошибка слияния термина {english_term}: {e}")
        
        return merged_count
    
    @staticmethod
    def validate_term_data(data: Dict) -> Dict[str, List[str]]:
        """Валидация данных термина"""
        errors = []
        
        if not data.get('english_term'):
            errors.append('Английский термин обязателен')
        
        if not data.get('russian_term'):
            errors.append('Русский термин обязателен')
        
        if not data.get('category'):
            errors.append('Категория обязательна')
        elif data['category'] not in ['characters', 'locations', 'terms', 'techniques', 'artifacts']:
            errors.append('Неверная категория')
        
        if data.get('first_appearance_chapter') is not None:
            try:
                chapter = int(data['first_appearance_chapter'])
                if chapter < 1:
                    errors.append('Номер главы должен быть положительным числом')
            except ValueError:
                errors.append('Номер главы должен быть числом')
        
        return {'errors': errors, 'valid': len(errors) == 0}
    
    @staticmethod
    def get_categories() -> List[str]:
        """Получение списка доступных категорий"""
        return ['characters', 'locations', 'terms', 'techniques', 'artifacts']
    
    @staticmethod
    def get_category_display_name(category: str) -> str:
        """Получение отображаемого названия категории"""
        names = {
            'characters': 'Персонажи',
            'locations': 'Локации',
            'terms': 'Термины',
            'techniques': 'Техники',
            'artifacts': 'Артефакты'
        }
        return names.get(category, category)
    
    @staticmethod
    def increment_usage(term_id: int) -> bool:
        """Увеличение счетчика использования термина"""
        term = GlossaryItem.query.get(term_id)
        if not term:
            return False
        
        term.increment_usage()
        return True
    
    @staticmethod
    def get_most_used_terms(novel_id: int, limit: int = 10) -> List[GlossaryItem]:
        """Получение наиболее используемых терминов"""
        return GlossaryItem.query.filter_by(
            novel_id=novel_id,
            is_active=True
        ).order_by(GlossaryItem.usage_count.desc()).limit(limit).all()
    
    @staticmethod
    def get_recently_added_terms(novel_id: int, limit: int = 10) -> List[GlossaryItem]:
        """Получение недавно добавленных терминов"""
        return GlossaryItem.query.filter_by(
            novel_id=novel_id,
            is_active=True
        ).order_by(GlossaryItem.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def clear_glossary(novel_id: int) -> int:
        """Очистка всего глоссария новеллы (полное удаление)"""
        # Удаляем все термины для данной новеллы
        count = GlossaryItem.query.filter_by(
            novel_id=novel_id
        ).delete()
        
        db.session.commit()
        return count 