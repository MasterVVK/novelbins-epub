#!/usr/bin/env python3
"""
Тестирование оптимизатора глоссария
"""
import sys
sys.path.insert(0, '/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.models import Novel, GlossaryItem
from app.services.glossary_optimizer import GlossaryOptimizer
import json

def test_optimizer():
    """Тестирование оптимизатора на новелле ISSTH"""
    
    app = create_app()
    with app.app_context():
        # Найти новеллу
        novel = Novel.query.filter(Novel.title.like('%запечатать%')).first()
        
        if not novel:
            print("❌ Новелла 'Я хочу запечатать небеса' не найдена")
            return
        
        print(f"✅ Найдена новелла: {novel.title} (ID: {novel.id})")
        
        # Анализ глоссария
        print("\n📊 АНАЛИЗ ГЛОССАРИЯ")
        print("=" * 60)
        
        stats = GlossaryOptimizer.optimize_novel_glossary(novel.id, auto_remove=False)
        
        print(f"Всего терминов: {stats['total']}")
        print(f"Для удаления: {len(stats['to_remove'])} ({stats.get('remove_percent', 0):.1f}%)")
        print(f"Для сохранения: {len(stats['to_keep'])} ({stats.get('keep_percent', 0):.1f}%)")
        print(f"Требуют проверки: {len(stats['to_review'])} ({stats.get('review_percent', 0):.1f}%)")
        
        # Примеры терминов для удаления
        if stats['to_remove']:
            print("\n🗑️ ПРИМЕРЫ ТЕРМИНОВ ДЛЯ УДАЛЕНИЯ:")
            print("-" * 40)
            for term in stats['to_remove'][:10]:
                print(f"  [{term['category']}] {term['chinese']} → {term['russian']}")
        
        # Примеры терминов для проверки
        if stats['to_review']:
            print("\n⚠️ ТЕРМИНЫ, ТРЕБУЮЩИЕ ПРОВЕРКИ:")
            print("-" * 40)
            for term in stats['to_review'][:5]:
                print(f"  [{term['category']}] {term['chinese']} → {term['russian']}")
        
        # Получение предложений
        print("\n💡 ПРЕДЛОЖЕНИЯ ПО ОПТИМИЗАЦИИ:")
        print("-" * 40)
        
        suggestions = GlossaryOptimizer.get_optimization_suggestions(novel.id, limit=10)
        
        for suggestion in suggestions:
            print(f"  [{suggestion['recommendation']}] {suggestion['chinese']} → {suggestion['russian']}")
            print(f"    Причина: {suggestion['reason']}")
        
        # Тест конкретных терминов
        print("\n🔍 ТЕСТ КОНКРЕТНЫХ ТЕРМИНОВ:")
        print("-" * 40)
        
        test_terms = [
            ('啊', 'ах', 'emotions_and_sounds'),
            ('修炼', 'культивация', 'cultivation_terms'),
            ('年', 'год', 'time_periods'),
            ('孟浩', 'Мэн Хао', 'characters'),
            ('灵石', 'духовные камни', 'currency')
        ]
        
        for chinese, russian, category in test_terms:
            # Создаем временный объект для теста
            test_item = GlossaryItem(
                english_term=chinese,
                russian_term=russian,
                category=category,
                novel_id=novel.id
            )
            
            result = GlossaryOptimizer.analyze_glossary_item(test_item)
            print(f"  {chinese} → {russian}: {result}")
        
        print("\n✅ Тестирование завершено!")
        
        # Сохранение отчета
        report = {
            'novel': novel.title,
            'statistics': {
                'total': stats['total'],
                'to_remove': len(stats['to_remove']),
                'to_keep': len(stats['to_keep']),
                'to_review': len(stats['to_review'])
            },
            'remove_examples': stats['to_remove'][:20],
            'review_examples': stats['to_review'][:10],
            'suggestions': suggestions
        }
        
        with open('/home/user/novelbins-epub/glossary_optimizer_test_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 Отчет сохранен в glossary_optimizer_test_report.json")

if __name__ == '__main__':
    test_optimizer()