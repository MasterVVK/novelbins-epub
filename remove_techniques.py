#!/usr/bin/env python3
"""
Удаление лишних техник из глоссария
"""
import sys
sys.path.insert(0, '/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, GlossaryItem
import re

def remove_techniques():
    """Удаление простых и общих техник"""
    
    app = create_app()
    with app.app_context():
        novel = Novel.query.filter(Novel.title.like('%запечатать%')).first()
        
        if not novel:
            print("❌ Новелла не найдена")
            return
        
        print(f"✅ Удаление техник для: {novel.title}")
        
        # Получаем все активные техники
        techniques = GlossaryItem.query.filter_by(
            novel_id=novel.id,
            category='techniques',
            is_active=True
        ).all()
        
        print(f"\n📊 Всего активных техник: {len(techniques)}")
        
        # Критерии для удаления
        remove_criteria = {
            # Простые элементальные атаки
            'simple_elemental': [
                r'водн.* шар', r'огнен.* шар', r'ветрян.* лезвие', r'громов.* шар',
                r'огнен.* зме[яи]', r'туманн.* зме[яи]', r'световой столб',
                r'дождев.* стрел', r'огнен.* питон', r'мечев.* дождь'
            ],
            # Простые физические действия
            'simple_physical': [
                r'^удар', r'^атака', r'^бросок', r'^толчок', r'^прыжок',
                r'^блок', r'^защита', r'^уклонение', r'^рывок'
            ],
            # Общие боевые техники
            'generic_combat': [
                r'полет на мече', r'защитн.* барьер', r'защитн.* шторм',
                r'световой барьер', r'золот.* барьер', r'контратака',
                r'коллапс и взрыв', r'один удар', r'скрыт.* атака'
            ],
            # Цветовые вариации без специфики
            'color_variations': [
                r'^пурпурн.* вихрь$', r'^черн.* шторм$', r'^золот.* лев$',
                r'^пурпурн.* ладонь$', r'^черн.* скорпион$'
            ]
        }
        
        # Ключевые слова для СОХРАНЕНИЯ техник
        keep_keywords = [
            'искусство', 'массив', 'формация', 'печать', 'сутра',
            'метод', 'путь', 'дао', 'трансформация', 'превращение',
            'божествен', 'небесн', 'демонич', 'дьявольск', 'древн',
            'бессмертн', 'запретн', 'тайн', 'секретн', 'великий'
        ]
        
        to_remove = []
        kept_important = []
        
        for tech in techniques:
            russian_lower = tech.russian_term.lower()
            chinese = tech.english_term
            
            # Проверяем важные техники (всегда сохраняем)
            if any(kw in russian_lower for kw in keep_keywords):
                kept_important.append(tech)
                continue
            
            # Проверяем критерии удаления
            should_remove = False
            removal_reason = ""
            
            # Проверка по категориям
            for category, patterns in remove_criteria.items():
                for pattern in patterns:
                    if re.search(pattern, russian_lower):
                        should_remove = True
                        removal_reason = category
                        break
                if should_remove:
                    break
            
            # Дополнительные проверки
            if not should_remove:
                # Короткие названия без специфики (2 символа)
                if len(chinese) <= 2:
                    should_remove = True
                    removal_reason = "short_generic"
                # Простые числовые техники
                elif re.search(r'^(перв|втор|трет|четверт|пят).* удар', russian_lower):
                    should_remove = True
                    removal_reason = "numbered_strikes"
            
            if should_remove:
                to_remove.append((tech, removal_reason))
        
        # Вывод статистики
        print(f"\n📋 АНАЛИЗ ЗАВЕРШЕН:")
        print(f"  - Техник для удаления: {len(to_remove)}")
        print(f"  - Важных техник сохранено: {len(kept_important)}")
        print(f"  - Останется техник: {len(techniques) - len(to_remove)}")
        
        # Примеры техник для удаления по категориям
        print(f"\n🗑️ ПРИМЕРЫ ТЕХНИК ДЛЯ УДАЛЕНИЯ:")
        
        categories_count = {}
        for tech, reason in to_remove[:30]:
            if reason not in categories_count:
                categories_count[reason] = 0
                print(f"\n  [{reason}]:")
            if categories_count[reason] < 5:
                print(f"    {tech.english_term} → {tech.russian_term}")
                categories_count[reason] += 1
        
        # Выполнение удаления
        print(f"\n🗑️ Удаление {len(to_remove)} техник...")
        
        removed_count = 0
        for tech, _ in to_remove:
            tech.is_active = False
            removed_count += 1
        
        db.session.commit()
        
        # Финальная статистика
        remaining = GlossaryItem.query.filter_by(
            novel_id=novel.id,
            category='techniques', 
            is_active=True
        ).count()
        
        print(f"\n✅ УДАЛЕНИЕ ЗАВЕРШЕНО!")
        print(f"  - Удалено техник: {removed_count}")
        print(f"  - Осталось активных техник: {remaining}")
        print(f"  - Процент удаления: {removed_count/len(techniques)*100:.1f}%")
        
        # Сохранение отчета
        with open('/home/user/novelbins-epub/techniques_removal_report.txt', 'w', encoding='utf-8') as f:
            f.write(f"ОТЧЕТ ОБ УДАЛЕНИИ ТЕХНИК\n")
            f.write(f"{'=' * 50}\n\n")
            f.write(f"Было техник: {len(techniques)}\n")
            f.write(f"Удалено: {removed_count}\n")
            f.write(f"Осталось: {remaining}\n\n")
            
            f.write("УДАЛЕННЫЕ ТЕХНИКИ ПО КАТЕГОРИЯМ:\n")
            current_reason = None
            for tech, reason in to_remove:
                if reason != current_reason:
                    f.write(f"\n[{reason}]\n")
                    current_reason = reason
                f.write(f"  {tech.english_term} → {tech.russian_term}\n")
        
        print(f"\n💾 Отчет сохранен в techniques_removal_report.txt")

if __name__ == '__main__':
    remove_techniques()