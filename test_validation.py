#!/usr/bin/env python3
import sqlite3
import sys
import re

def validate_translation(original: str, translated: str, chapter_num: int):
    """Упрощенная версия валидации для тестирования"""
    issues = []
    warnings = []
    critical_issues = []

    # Проверка соотношения длины
    orig_len = len(original)
    trans_len = len(translated)
    ratio = trans_len / orig_len if orig_len > 0 else 0

    if ratio < 0.6:
        critical_issues.append(f"Перевод слишком короткий: {ratio:.2f} от оригинала")
    elif ratio < 0.9:
        issues.append(f"Перевод короткий: {ratio:.2f} от оригинала")

    # Проверка количества абзацев
    orig_normalized = re.sub(r'\n\s*\n', '\n\n', original.strip())
    trans_normalized = re.sub(r'\n\s*\n', '\n\n', translated.strip())
    
    orig_paragraphs = len([p for p in orig_normalized.split('\n\n') if p.strip()])
    trans_paragraphs = len([p for p in trans_normalized.split('\n\n') if p.strip()])
    
    # Проверка на тексты с одинарными переносами
    single_newlines_orig = original.count('\n')
    double_newlines_orig = original.count('\n\n')
    
    print(f"Оригинал: {single_newlines_orig} одинарных переносов, {double_newlines_orig} двойных")
    print(f"Изначально: {orig_paragraphs} абзацев в оригинале, {trans_paragraphs} в переводе")
    
    para_ratio = trans_paragraphs / orig_paragraphs if orig_paragraphs > 0 else 0
    
    # Корректировка для текстов с одинарными переносами
    if single_newlines_orig > double_newlines_orig * 3:
        orig_lines = len([line for line in original.split('\n') if line.strip() and len(line.strip()) > 5])
        trans_lines = len([line for line in translated.split('\n') if line.strip() and len(line.strip()) > 5])
        orig_paragraphs_initial = len([p for p in re.sub(r'\n\s*\n', '\n\n', original.strip()).split('\n\n') if p.strip()])
        
        print(f"Обнаружен формат с одинарными переносами: {orig_lines} строк")
        print(f"orig_lines ({orig_lines}) > orig_paragraphs_initial ({orig_paragraphs_initial}) * 2 = {orig_lines > orig_paragraphs_initial * 2}")
        
        if orig_lines > orig_paragraphs_initial * 2 and trans_paragraphs > 20 and trans_len > orig_len * 0.7:
            # Переопределяем para_ratio для таких случаев
            para_ratio = 1.0
            print(f"✅ Применена мягкая валидация: {trans_paragraphs} абзацев в переводе, длина {ratio:.2f}")

    # Проверка соотношения абзацев
    if para_ratio < 0.6:
        critical_issues.append(f"Критическая разница в абзацах: {orig_paragraphs} → {trans_paragraphs} ({para_ratio:.1%})")

    return {
        'critical': critical_issues,
        'issues': issues,
        'warnings': warnings,
        'valid': len(critical_issues) == 0
    }

# Получаем главу из БД
conn = sqlite3.connect('/home/user/novelbins-epub/web_app/instance/novel_translator.db')
cursor = conn.cursor()
cursor.execute('SELECT original_text FROM chapters WHERE chapter_number = 1110 LIMIT 1')
row = cursor.fetchone()

if row:
    original_text = row[0]
    print(f'Тестируем главу 1110')
    print(f'Длина оригинала: {len(original_text)} символов')
    print(f'Количество строк: {len(original_text.splitlines())}')
    print('-' * 50)
    
    # Создаем перевод с 49 абзацами (как в реальном переводе)
    test_translation = ''
    for i in range(49):
        test_translation += f'Это тестовый абзац номер {i+1}. Он содержит достаточно текста для прохождения валидации и имитирует реальный перевод главы. ' * 5
        test_translation += '\n\n'
    
    para_count = len([p for p in test_translation.split("\n\n") if p.strip()])
    print(f'\nТестовый перевод: {len(test_translation)} символов, {para_count} абзацев')
    print('-' * 50)
    
    validation = validate_translation(original_text, test_translation, 1110)
    
    print(f'\nРезультат валидации:')
    print(f'  Критические проблемы: {validation.get("critical", [])}')
    print(f'  Проблемы: {validation.get("issues", [])}')
    print(f'  Предупреждения: {validation.get("warnings", [])}')
    
    if validation.get('valid'):
        print('\n✅ Валидация прошла успешно!')
    else:
        print('\n❌ Валидация не пройдена')
else:
    print('Глава 1110 не найдена')

conn.close()