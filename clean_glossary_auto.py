#!/usr/bin/env python3
"""
Автоматическая очистка глоссария без подтверждения
"""
import sys
sys.path.insert(0, '/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, GlossaryItem
from app.services.glossary_optimizer import GlossaryOptimizer

def clean_glossary():
    """Автоматическая очистка глоссария новеллы ISSTH"""
    
    app = create_app()
    with app.app_context():
        # Найти новеллу
        novel = Novel.query.filter(Novel.title.like('%запечатать%')).first()
        
        if not novel:
            print("❌ Новелла 'Я хочу запечатать небеса' не найдена")
            return
        
        print(f"✅ Найдена новелла: {novel.title} (ID: {novel.id})")
        
        # Подсчет терминов до очистки
        total_before = GlossaryItem.query.filter_by(novel_id=novel.id, is_active=True).count()
        print(f"\n📊 Терминов до очистки: {total_before}")
        
        # Анализ перед удалением
        print("\n🔍 Анализ глоссария...")
        stats = GlossaryOptimizer.optimize_novel_glossary(novel.id, auto_remove=False)
        
        print(f"  - Для удаления: {len(stats['to_remove'])}")
        print(f"  - Для сохранения: {len(stats['to_keep'])}")
        print(f"  - Требуют проверки: {len(stats['to_review'])}")
        
        # Примеры терминов для удаления
        print("\n📋 Примеры терминов для удаления:")
        for i, term in enumerate(stats['to_remove'][:20], 1):
            print(f"  {i}. [{term['category']}] {term['chinese']} → {term['russian']}")
        
        # Выполнение удаления БЕЗ подтверждения
        print(f"\n🗑️ Удаление {len(stats['to_remove'])} терминов...")
        removed_count = GlossaryOptimizer.batch_remove_direct_translations(novel.id)
        
        # Подсчет после очистки
        total_after = GlossaryItem.query.filter_by(novel_id=novel.id, is_active=True).count()
        
        print(f"\n✅ Удаление завершено!")
        print(f"  - Удалено терминов: {removed_count}")
        print(f"  - Осталось активных: {total_after}")
        print(f"  - Было деактивировано: {total_before - total_after}")
        
        # Статистика по категориям
        print("\n📈 Статистика по категориям после очистки:")
        categories = db.session.query(
            GlossaryItem.category,
            db.func.count(GlossaryItem.id).label('count')
        ).filter_by(
            novel_id=novel.id,
            is_active=True
        ).group_by(GlossaryItem.category).all()
        
        total_remaining = 0
        for category, count in sorted(categories, key=lambda x: x[1], reverse=True):
            print(f"  - {category}: {count}")
            total_remaining += count
        
        print(f"\n📊 Итого активных терминов: {total_remaining}")
        
        # Сохранение статистики
        with open('/home/user/novelbins-epub/glossary_cleanup_stats.txt', 'w', encoding='utf-8') as f:
            f.write(f"Очистка глоссария для: {novel.title}\n")
            f.write(f"Было терминов: {total_before}\n")
            f.write(f"Удалено: {removed_count}\n")
            f.write(f"Осталось: {total_after}\n")
            f.write(f"\nПо категориям:\n")
            for category, count in sorted(categories, key=lambda x: x[1], reverse=True):
                f.write(f"  {category}: {count}\n")
        
        print("\n💾 Статистика сохранена в glossary_cleanup_stats.txt")
        print("💡 Деактивированные термины можно восстановить через API")

if __name__ == '__main__':
    clean_glossary()