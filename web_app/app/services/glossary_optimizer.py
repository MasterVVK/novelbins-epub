"""
Сервис оптимизации глоссария для удаления терминов с однозначным переводом
"""
import re
from typing import Dict, List, Tuple, Set
from app.models import GlossaryItem
from app import db

class GlossaryOptimizer:
    """Оптимизатор глоссария для новелл"""
    
    # Термины с прямым переводом для удаления
    DIRECT_TRANSLATIONS = {
        '年': 'год',
        '月': 'месяц', 
        '日': 'день',
        '天': 'небо',
        '地': 'земля',
        '水': 'вода',
        '火': 'огонь',
        '风': 'ветер',
        '山': 'гора',
        '人': 'человек',
        '心': 'сердце',
        '手': 'рука',
        '头': 'голова',
        '眼': 'глаз',
        '口': 'рот',
        '红': 'красный',
        '蓝': 'синий',
        '绿': 'зелёный',
        '黄': 'жёлтый',
        '白': 'белый',
        '黑': 'чёрный'
    }
    
    # Звукоподражания для автоматического удаления
    SOUND_PATTERNS = [
        r'^[啊哈呵嗯咳轰砰嗡咔噗哼唉哦呃]+$',
        r'^(ха|хе|мм|хм|кхе|бум|бах|пух|фырк|ах|ох|эх|ух).*$'
    ]
    
    # Ключевые слова культивации - ВСЕГДА сохранять
    CULTIVATION_KEYWORDS = [
        'культивац', 'ци', 'дао', 'душ', 'ядр', 'меридиан',
        'даньтянь', 'пилюл', 'алхим', 'артефакт', 'сокровищ',
        'техник', 'заклинан', 'секта', 'старейшин', 'печат',
        'бессмерт', 'небесн', 'божествен', 'духовн', 'карм',
        'основ', 'прорыв', 'трибулац', 'формирован'
    ]
    
    # Китайские иероглифы, указывающие на важность термина
    IMPORTANT_CHINESE_CHARS = [
        '修', '炼', '仙', '道', '气', '丹', '灵', '神',
        '元', '真', '法', '宝', '术', '功', '脉', '宗',
        '魔', '妖', '煞', '阵', '符', '诀', '境', '劫'
    ]
    
    @classmethod
    def is_direct_translation(cls, chinese: str, russian: str, category: str = None) -> bool:
        """Проверка, является ли перевод прямым/однозначным"""
        
        # НИКОГДА не удаляем персонажей
        if category and category in ['characters', 'character']:
            return False
        
        # Проверка на имена - если есть заглавные буквы в середине слова, это имя
        if any(char.isupper() for char in russian[1:]) and not russian.isupper():
            return False
        
        # Проверка прямых переводов
        if chinese in cls.DIRECT_TRANSLATIONS:
            return True
        
        # Проверка звукоподражаний
        for pattern in cls.SOUND_PATTERNS:
            if re.match(pattern, chinese) or re.match(pattern, russian.lower()):
                return True
        
        # Проверка чисел
        if chinese.isdigit() or russian.replace(' ', '').isdigit():
            return True
        
        # Короткие общие слова (1-2 символа без специфики)
        if len(chinese) <= 2 and not any(char in chinese for char in cls.IMPORTANT_CHINESE_CHARS):
            # Проверяем, что это не имя персонажа или важный термин
            if not any(keyword in russian.lower() for keyword in cls.CULTIVATION_KEYWORDS):
                # Дополнительная проверка на имена
                if not any(name_part in russian for name_part in ['Мэн', 'Ван', 'Ли', 'Чжан', 'Лю', 'Чэнь', 'Ян', 'Хуан', 'Чжао', 'У', 'Чжоу', 'Сюй', 'Сунь', 'Ма', 'Чжу', 'Ху', 'Линь', 'Хэ', 'Гао', 'Ло']):
                    return True
        
        return False
    
    @classmethod
    def is_important_term(cls, chinese: str, russian: str) -> bool:
        """Проверка, является ли термин важным для контекста новеллы"""
        
        russian_lower = russian.lower()
        
        # Проверка ключевых слов культивации
        for keyword in cls.CULTIVATION_KEYWORDS:
            if keyword in russian_lower:
                return True
        
        # Проверка важных китайских иероглифов
        for char in cls.IMPORTANT_CHINESE_CHARS:
            if char in chinese:
                return True
        
        # Имена персонажей всегда важны
        if any(title in russian_lower for title in ['господин', 'госпожа', 'старш', 'младш', 'учител', 'мастер']):
            return True
        
        # Названия локаций с сектами/кланами
        if any(word in russian_lower for word in ['секта', 'клан', 'дворец', 'павильон', 'долина', 'пик']):
            return True
        
        return False
    
    @classmethod
    def analyze_glossary_item(cls, item: GlossaryItem) -> str:
        """
        Анализ элемента глоссария
        Возвращает: 'remove', 'keep', или 'review'
        """
        chinese = item.english_term  # В модели english_term содержит китайский
        russian = item.russian_term
        category = item.category
        
        # Сначала проверяем важность
        if cls.is_important_term(chinese, russian):
            return 'keep'
        
        # Затем проверяем на прямой перевод с учетом категории
        if cls.is_direct_translation(chinese, russian, category):
            return 'remove'
        
        # Если неясно - помечаем для ручной проверки
        return 'review'
    
    @classmethod
    def optimize_novel_glossary(cls, novel_id: int, auto_remove: bool = False) -> Dict:
        """
        Оптимизация глоссария новеллы
        
        Args:
            novel_id: ID новеллы
            auto_remove: Автоматически удалять термины с прямым переводом
        
        Returns:
            Словарь со статистикой оптимизации
        """
        items = GlossaryItem.query.filter_by(novel_id=novel_id, is_active=True).all()
        
        stats = {
            'total': len(items),
            'to_remove': [],
            'to_keep': [],
            'to_review': [],
            'removed': 0
        }
        
        for item in items:
            result = cls.analyze_glossary_item(item)
            
            if result == 'remove':
                stats['to_remove'].append({
                    'id': item.id,
                    'chinese': item.english_term,
                    'russian': item.russian_term,
                    'category': item.category
                })
                
                if auto_remove:
                    item.is_active = False  # Деактивируем вместо удаления
                    stats['removed'] += 1
                    
            elif result == 'keep':
                stats['to_keep'].append({
                    'id': item.id,
                    'chinese': item.english_term,
                    'russian': item.russian_term,
                    'category': item.category
                })
            else:
                stats['to_review'].append({
                    'id': item.id,
                    'chinese': item.english_term,
                    'russian': item.russian_term,
                    'category': item.category
                })
        
        if auto_remove and stats['removed'] > 0:
            db.session.commit()
        
        # Подсчет процентов
        if stats['total'] > 0:
            stats['remove_percent'] = len(stats['to_remove']) / stats['total'] * 100
            stats['keep_percent'] = len(stats['to_keep']) / stats['total'] * 100
            stats['review_percent'] = len(stats['to_review']) / stats['total'] * 100
        
        return stats
    
    @classmethod
    def batch_remove_direct_translations(cls, novel_id: int) -> int:
        """
        Пакетное удаление терминов с прямым переводом
        
        Returns:
            Количество удаленных терминов
        """
        items = GlossaryItem.query.filter_by(novel_id=novel_id, is_active=True).all()
        removed_count = 0
        
        for item in items:
            if cls.is_direct_translation(item.english_term, item.russian_term, item.category):
                item.is_active = False
                removed_count += 1
        
        if removed_count > 0:
            db.session.commit()
        
        return removed_count
    
    @classmethod
    def get_optimization_suggestions(cls, novel_id: int, limit: int = 20) -> List[Dict]:
        """
        Получение предложений по оптимизации глоссария
        
        Returns:
            Список терминов с рекомендациями
        """
        items = GlossaryItem.query.filter_by(
            novel_id=novel_id, 
            is_active=True
        ).limit(limit).all()
        
        suggestions = []
        
        for item in items:
            result = cls.analyze_glossary_item(item)
            
            if result in ['remove', 'review']:
                suggestion = {
                    'id': item.id,
                    'chinese': item.english_term,
                    'russian': item.russian_term,
                    'category': item.category,
                    'recommendation': result,
                    'reason': ''
                }
                
                if result == 'remove':
                    if item.english_term in cls.DIRECT_TRANSLATIONS:
                        suggestion['reason'] = 'Прямой перевод общеупотребительного слова'
                    elif any(re.match(p, item.english_term) for p in cls.SOUND_PATTERNS):
                        suggestion['reason'] = 'Звукоподражание'
                    else:
                        suggestion['reason'] = 'Простое слово без культивационной специфики'
                else:
                    suggestion['reason'] = 'Требует ручной проверки'
                
                suggestions.append(suggestion)
        
        return suggestions
    
    @classmethod
    def restore_removed_terms(cls, novel_id: int, term_ids: List[int] = None) -> int:
        """
        Восстановление удаленных терминов
        
        Args:
            novel_id: ID новеллы
            term_ids: Список ID терминов для восстановления (None = все)
        
        Returns:
            Количество восстановленных терминов
        """
        query = GlossaryItem.query.filter_by(novel_id=novel_id, is_active=False)
        
        if term_ids:
            query = query.filter(GlossaryItem.id.in_(term_ids))
        
        items = query.all()
        restored_count = len(items)
        
        for item in items:
            item.is_active = True
        
        if restored_count > 0:
            db.session.commit()
        
        return restored_count