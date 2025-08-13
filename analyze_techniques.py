#!/usr/bin/env python3
"""
Анализ техник в глоссарии для определения лишних
"""
import sys
sys.path.insert(0, '/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, GlossaryItem
from collections import Counter, defaultdict
import re

def analyze_techniques():
    """Анализ техник в глоссарии"""
    
    app = create_app()
    with app.app_context():
        novel = Novel.query.filter(Novel.title.like('%запечатать%')).first()
        
        if not novel:
            print("❌ Новелла не найдена")
            return
        
        print(f"✅ Анализ техник для: {novel.title}")
        
        # Получаем все активные техники
        techniques = GlossaryItem.query.filter_by(
            novel_id=novel.id,
            category='techniques',
            is_active=True
        ).all()
        
        print(f"\n📊 Всего техник: {len(techniques)}")
        
        # Категоризация техник
        generic_techniques = []  # Общие техники
        specific_techniques = []  # Специфичные техники
        simple_actions = []  # Простые действия
        duplicate_similar = defaultdict(list)  # Похожие/дублирующиеся
        
        # Ключевые слова для общих техник
        generic_keywords = [
            'удар', 'атака', 'взрыв', 'волна', 'луч', 'щит', 'барьер',
            'прыжок', 'полет', 'скорость', 'сила', 'защита', 'блок',
            'уклонение', 'бросок', 'толчок', 'рывок', 'ускорение'
        ]
        
        # Ключевые слова для важных техник
        important_keywords = [
            'печать', 'формация', 'массив', 'заклинание', 'искусство',
            'метод', 'путь', 'дао', 'трансформация', 'превращение',
            'божественн', 'небесн', 'демонич', 'дьявольск', 'драконь',
            'феникс', 'бессмертн', 'запретн', 'тайн', 'древн'
        ]
        
        print("\n🔍 Анализ техник...")
        
        for tech in techniques:
            chinese = tech.english_term
            russian = tech.russian_term.lower()
            
            # Проверка на простые действия
            if len(chinese) <= 2 and not any(kw in russian for kw in important_keywords):
                simple_actions.append(tech)
            # Проверка на общие техники
            elif any(kw in russian for kw in generic_keywords) and not any(kw in russian for kw in important_keywords):
                generic_techniques.append(tech)
            # Специфичные техники
            elif any(kw in russian for kw in important_keywords):
                specific_techniques.append(tech)
            else:
                # Группировка похожих
                base_name = russian.split()[0] if russian.split() else russian
                duplicate_similar[base_name].append(tech)
        
        # Вывод результатов
        print(f"\n📋 РЕЗУЛЬТАТЫ АНАЛИЗА:")
        print(f"  - Простые действия: {len(simple_actions)}")
        print(f"  - Общие техники: {len(generic_techniques)}")
        print(f"  - Специфичные техники: {len(specific_techniques)}")
        print(f"  - Группы похожих: {len([g for g in duplicate_similar.values() if len(g) > 1])}")
        
        # Примеры простых действий для удаления
        if simple_actions:
            print(f"\n🗑️ ПРОСТЫЕ ДЕЙСТВИЯ (рекомендуется удалить):")
            for i, tech in enumerate(simple_actions[:20], 1):
                print(f"  {i}. {tech.english_term} → {tech.russian_term}")
        
        # Примеры общих техник
        if generic_techniques:
            print(f"\n⚠️ ОБЩИЕ ТЕХНИКИ (возможно удалить):")
            for i, tech in enumerate(generic_techniques[:20], 1):
                print(f"  {i}. {tech.english_term} → {tech.russian_term}")
        
        # Примеры дублирующихся
        print(f"\n🔄 ПОХОЖИЕ/ДУБЛИРУЮЩИЕСЯ ТЕХНИКИ:")
        count = 0
        for base, techs in duplicate_similar.items():
            if len(techs) > 1 and count < 10:
                print(f"\n  Группа '{base}':")
                for tech in techs[:5]:
                    print(f"    - {tech.english_term} → {tech.russian_term}")
                count += 1
        
        # Примеры важных техник (сохранить)
        if specific_techniques:
            print(f"\n✅ ВАЖНЫЕ ТЕХНИКИ (обязательно сохранить):")
            for i, tech in enumerate(specific_techniques[:10], 1):
                print(f"  {i}. {tech.english_term} → {tech.russian_term}")
        
        # Статистика по длине названий
        print(f"\n📏 СТАТИСТИКА ПО ДЛИНЕ:")
        length_stats = Counter(len(t.english_term) for t in techniques)
        for length in sorted(length_stats.keys())[:10]:
            print(f"  {length} символов: {length_stats[length]} техник")
        
        # Подсчет потенциального удаления
        to_remove_count = len(simple_actions) + len(generic_techniques)
        print(f"\n🎯 ИТОГО:")
        print(f"  Рекомендуется удалить: {to_remove_count} техник")
        print(f"  Процент от общего: {to_remove_count/len(techniques)*100:.1f}%")
        print(f"  Останется: {len(techniques) - to_remove_count} техник")
        
        # Сохранение списка для удаления
        with open('/home/user/novelbins-epub/techniques_to_remove.txt', 'w', encoding='utf-8') as f:
            f.write("ТЕХНИКИ ДЛЯ УДАЛЕНИЯ\n")
            f.write("=" * 50 + "\n\n")
            
            f.write("ПРОСТЫЕ ДЕЙСТВИЯ:\n")
            for tech in simple_actions:
                f.write(f"{tech.id}\t{tech.english_term}\t{tech.russian_term}\n")
            
            f.write("\nОБЩИЕ ТЕХНИКИ:\n")
            for tech in generic_techniques:
                f.write(f"{tech.id}\t{tech.english_term}\t{tech.russian_term}\n")
        
        print(f"\n💾 Список техник для удаления сохранен в techniques_to_remove.txt")
        
        return {
            'simple_actions': [t.id for t in simple_actions],
            'generic_techniques': [t.id for t in generic_techniques]
        }

if __name__ == '__main__':
    analyze_techniques()