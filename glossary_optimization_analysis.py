#!/usr/bin/env python3
"""
Анализ глоссария ISSTH для оптимизации и удаления терминов с однозначным переводом
"""

import json
import re
from typing import Dict, List, Tuple, Set
from collections import defaultdict

def load_glossary(file_path: str) -> Dict:
    """Загрузка глоссария из JSON файла"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def is_direct_translation(chinese: str, russian: str) -> bool:
    """
    Проверка, является ли перевод однозначным (прямым)
    Критерии:
    1. Короткие общеупотребительные слова (год, месяц, день и т.д.)
    2. Междометия и звукоподражания
    3. Числительные и измерения
    4. Простые цвета
    5. Базовые временные периоды
    """
    
    # Простые общеупотребительные слова
    direct_translations = {
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
        '口': 'рот'
    }
    
    # Звукоподражания и междометия - всегда прямой перевод
    sound_patterns = [
        r'^[啊哈呵嗯咳轰砰嗡咔噗哼唉哦呃]+',
        r'^(ха|хе|мм|хм|кхе|бум|бах|пух|фырк)'
    ]
    
    # Проверка на звукоподражания
    for pattern in sound_patterns:
        if re.match(pattern, chinese) or re.match(pattern, russian, re.IGNORECASE):
            return True
    
    # Проверка на простые цвета (без метафорического значения)
    basic_colors = {
        '红': 'красный',
        '蓝': 'синий',
        '绿': 'зелёный',
        '黄': 'жёлтый',
        '白': 'белый',
        '黑': 'чёрный'
    }
    
    # Проверка прямых переводов
    if chinese in direct_translations:
        return True
    
    if chinese in basic_colors and basic_colors[chinese].lower() in russian.lower():
        return True
    
    # Проверка чисел
    if chinese.isdigit() or russian.isdigit():
        return True
    
    return False

def is_cultivation_specific_term(chinese: str, russian: str) -> bool:
    """
    Проверка, является ли термин специфичным для культивации
    Такие термины нужно СОХРАНИТЬ в глоссарии
    """
    
    # Ключевые слова культивации, которые нужно сохранить
    cultivation_keywords = [
        'культивац', 'ци', 'дао', 'душ', 'ядр', 'меридиан', 
        'даньтянь', 'пилюл', 'алхим', 'артефакт', 'сокровищ',
        'техник', 'заклинан', 'секта', 'старейшин', 'печат',
        'бессмерт', 'небесн', 'божествен', 'духовн', 'карм'
    ]
    
    russian_lower = russian.lower()
    for keyword in cultivation_keywords:
        if keyword in russian_lower:
            return True
    
    # Специальные китайские термины культивации
    cultivation_chinese = [
        '修', '炼', '仙', '道', '气', '丹', '灵', '神', 
        '元', '真', '法', '宝', '术', '功', '脉', '宗'
    ]
    
    for char in cultivation_chinese:
        if char in chinese:
            return True
    
    return False

def analyze_glossary(glossary: Dict) -> Tuple[Dict, Dict]:
    """
    Анализ глоссария и разделение на:
    1. Термины для удаления (однозначный перевод)
    2. Термины для сохранения (специфичные для культивации)
    """
    
    terms_to_remove = defaultdict(dict)
    terms_to_keep = defaultdict(dict)
    
    for category, terms in glossary.items():
        if category in ['novel_info', 'description', 'title']:
            continue
            
        for chinese, russian in (terms.items() if isinstance(terms, dict) else []):
            if is_direct_translation(chinese, russian):
                terms_to_remove[category][chinese] = russian
            elif is_cultivation_specific_term(chinese, russian):
                terms_to_keep[category][chinese] = russian
            else:
                # По умолчанию сохраняем термин, если не уверены
                terms_to_keep[category][chinese] = russian
    
    return dict(terms_to_remove), dict(terms_to_keep)

def create_optimized_glossary(original_glossary: Dict, terms_to_keep: Dict) -> Dict:
    """Создание оптимизированного глоссария"""
    
    optimized = {}
    
    # Сохраняем метаинформацию
    if 'novel_info' in original_glossary:
        optimized['novel_info'] = original_glossary['novel_info']
    
    # Добавляем только необходимые термины
    for category, terms in terms_to_keep.items():
        if terms:  # Добавляем категорию только если есть термины
            optimized[category] = terms
    
    return optimized

def generate_report(terms_to_remove: Dict, terms_to_keep: Dict) -> str:
    """Генерация отчета об оптимизации"""
    
    report = []
    report.append("=" * 80)
    report.append("ОТЧЕТ ОБ ОПТИМИЗАЦИИ ГЛОССАРИЯ ISSTH")
    report.append("=" * 80)
    report.append("")
    
    # Статистика
    total_removed = sum(len(terms) for terms in terms_to_remove.values())
    total_kept = sum(len(terms) for terms in terms_to_keep.values())
    total = total_removed + total_kept
    
    report.append(f"Общее количество терминов: {total}")
    report.append(f"Терминов для удаления: {total_removed} ({total_removed/total*100:.1f}%)")
    report.append(f"Терминов для сохранения: {total_kept} ({total_kept/total*100:.1f}%)")
    report.append("")
    
    # Термины для удаления
    report.append("-" * 40)
    report.append("ТЕРМИНЫ ДЛЯ УДАЛЕНИЯ (однозначный перевод):")
    report.append("-" * 40)
    
    for category, terms in terms_to_remove.items():
        if terms:
            report.append(f"\n{category.upper()}:")
            for chinese, russian in sorted(terms.items()):
                report.append(f"  {chinese} → {russian}")
    
    # Термины для сохранения (примеры)
    report.append("\n" + "-" * 40)
    report.append("ПРИМЕРЫ СОХРАНЕННЫХ ТЕРМИНОВ (специфичные для культивации):")
    report.append("-" * 40)
    
    examples_shown = 0
    for category, terms in terms_to_keep.items():
        if terms and examples_shown < 20:
            report.append(f"\n{category.upper()} (примеры):")
            for chinese, russian in list(terms.items())[:5]:
                report.append(f"  {chinese} → {russian}")
                examples_shown += 1
    
    return "\n".join(report)

def main():
    # Анализ основного глоссария
    print("Загрузка глоссариев...")
    
    glossary1 = load_glossary('/home/user/novelbins-epub/issth_glossary_chinese.json')
    glossary2 = load_glossary('/home/user/novelbins-epub/translation_templates/issth_glossary.json')
    
    print("\nАнализ глоссария issth_glossary_chinese.json...")
    remove1, keep1 = analyze_glossary(glossary1)
    
    print("Анализ глоссария issth_glossary.json...")
    remove2, keep2 = analyze_glossary(glossary2)
    
    # Генерация отчетов
    report1 = generate_report(remove1, keep1)
    report2 = generate_report(remove2, keep2)
    
    # Сохранение отчетов
    with open('/home/user/novelbins-epub/glossary_optimization_report.txt', 'w', encoding='utf-8') as f:
        f.write("АНАЛИЗ ФАЙЛА: issth_glossary_chinese.json\n")
        f.write(report1)
        f.write("\n\n")
        f.write("АНАЛИЗ ФАЙЛА: translation_templates/issth_glossary.json\n")
        f.write(report2)
    
    # Создание оптимизированных глоссариев
    optimized1 = create_optimized_glossary(glossary1, keep1)
    optimized2 = create_optimized_glossary(glossary2, keep2)
    
    # Сохранение оптимизированных глоссариев
    with open('/home/user/novelbins-epub/issth_glossary_optimized.json', 'w', encoding='utf-8') as f:
        json.dump(optimized1, f, ensure_ascii=False, indent=2)
    
    with open('/home/user/novelbins-epub/translation_templates/issth_glossary_optimized.json', 'w', encoding='utf-8') as f:
        json.dump(optimized2, f, ensure_ascii=False, indent=2)
    
    print("\n✅ Анализ завершен!")
    print(f"📊 Отчет сохранен в: glossary_optimization_report.txt")
    print(f"📚 Оптимизированные глоссарии:")
    print(f"   - issth_glossary_optimized.json")
    print(f"   - translation_templates/issth_glossary_optimized.json")
    
    # Вывод краткой статистики
    print(f"\n📈 Статистика оптимизации:")
    print(f"   Файл 1: удалено {sum(len(t) for t in remove1.values())} терминов из {sum(len(t) for t in glossary1.values()) if isinstance(glossary1, dict) else 0}")
    print(f"   Файл 2: удалено {sum(len(t) for t in remove2.values())} терминов из {sum(len(t) for t in glossary2.values()) if isinstance(glossary2, dict) else 0}")

if __name__ == '__main__':
    main()