#!/usr/bin/env python3
import sqlite3
import re

# Получаем главу из БД
conn = sqlite3.connect('/home/user/novelbins-epub/web_app/instance/novel_translator.db')
cursor = conn.cursor()
cursor.execute('SELECT original_text FROM chapters WHERE chapter_number = 1110 AND novel_id = 10')
original = cursor.fetchone()[0]
conn.close()

# Симулируем перевод с 49 абзацами
translated = ''
for i in range(49):
    translated += f'Это абзац номер {i+1}. Содержит достаточно текста для валидации. ' * 5
    translated += '\n\n'

print("=" * 60)
print("АНАЛИЗ ОРИГИНАЛЬНОГО ТЕКСТА")
print("=" * 60)

# Точная логика из валидатора
orig_len = len(original)
trans_len = len(translated)
ratio = trans_len / orig_len if orig_len > 0 else 0

print(f"Длина оригинала: {orig_len}")
print(f"Длина перевода: {trans_len}")
print(f"Соотношение длины: {ratio:.2f}")

# Подсчет абзацев - ТОЧНО КАК В КОДЕ
orig_normalized = re.sub(r'\n\s*\n', '\n\n', original.strip())
trans_normalized = re.sub(r'\n\s*\n', '\n\n', translated.strip())

orig_paragraphs = len([p for p in orig_normalized.split('\n\n') if p.strip()])
trans_paragraphs = len([p for p in trans_normalized.split('\n\n') if p.strip()])

print(f"\nИзначальные абзацы: оригинал={orig_paragraphs}, перевод={trans_paragraphs}")

# Проверка на одинарные переносы
single_newlines_orig = original.count('\n')
double_newlines_orig = original.count('\n\n')

print(f"\nОдинарные переносы: {single_newlines_orig}")
print(f"Двойные переносы: {double_newlines_orig}")
print(f"Соотношение: {single_newlines_orig / double_newlines_orig if double_newlines_orig else 0:.2f}")

# ПЕРВЫЙ БЛОК ПРОВЕРКИ (строки 1318-1338)
print("\n" + "=" * 60)
print("ПЕРВЫЙ БЛОК ЛОГИКИ (изменение orig_paragraphs)")
print("=" * 60)

if single_newlines_orig > double_newlines_orig * 1.8 and double_newlines_orig > 10:
    print(f"✓ Условие выполнено: {single_newlines_orig} > {double_newlines_orig * 1.8:.1f} и {double_newlines_orig} > 10")
    
    # Считаем ВСЕ непустые строки
    orig_lines = len([line for line in original.split('\n') if line.strip()])
    trans_lines = len([line for line in translated.split('\n') if line.strip()])
    
    print(f"Количество строк: оригинал={orig_lines}, перевод={trans_lines}")
    
    if orig_lines >= orig_paragraphs:
        print(f"✓ Условие orig_lines > orig_paragraphs: {orig_lines} > {orig_paragraphs}")
        
        if trans_paragraphs > 20 and trans_len > orig_len * 0.7:
            print(f"✓ Мягкая валидация: trans_paragraphs={trans_paragraphs} > 20 и trans_len={trans_len} > {orig_len * 0.7:.0f}")
            print("→ НЕ меняем orig_paragraphs")
        else:
            print(f"✗ Условие не выполнено: trans_paragraphs={trans_paragraphs}, trans_len={trans_len}")
            print(f"→ Меняем: orig_paragraphs {orig_paragraphs} → {orig_lines}")
            print(f"→ Меняем: trans_paragraphs {trans_paragraphs} → max({trans_paragraphs}, {trans_lines})")
            orig_paragraphs = orig_lines
            trans_paragraphs = max(trans_paragraphs, trans_lines)
    else:
        print(f"✗ Условие orig_lines > orig_paragraphs НЕ выполнено: {orig_lines} <= {orig_paragraphs}")
else:
    print(f"✗ Первое условие НЕ выполнено")

print(f"\nПосле первого блока: orig_paragraphs={orig_paragraphs}, trans_paragraphs={trans_paragraphs}")

# Расчет para_ratio (строки 1340-1341)
para_diff = abs(orig_paragraphs - trans_paragraphs)
para_ratio = trans_paragraphs / orig_paragraphs if orig_paragraphs > 0 else 0

print(f"\npara_diff = {para_diff}")
print(f"para_ratio = {para_ratio:.3f}")

# ВТОРОЙ БЛОК КОРРЕКТИРОВКИ (строки 1344-1354)
print("\n" + "=" * 60)
print("ВТОРОЙ БЛОК ЛОГИКИ (корректировка para_ratio)")
print("=" * 60)

if single_newlines_orig > double_newlines_orig * 1.8 and double_newlines_orig > 10:
    print(f"✓ Условие выполнено: {single_newlines_orig} > {double_newlines_orig * 1.8:.1f} и {double_newlines_orig} > 10")
    
    # Считаем ВСЕ непустые строки
    orig_lines = len([line for line in original.split('\n') if line.strip()])
    orig_paragraphs_initial = len([p for p in re.sub(r'\n\s*\n', '\n\n', original.strip()).split('\n\n') if p.strip()])
    
    min_trans_paragraphs = min(20, max(5, orig_paragraphs_initial // 3))
    
    print(f"orig_lines = {orig_lines}")
    print(f"orig_paragraphs_initial = {orig_paragraphs_initial}")
    print(f"min_trans_paragraphs = {min_trans_paragraphs}")
    
    if orig_lines >= orig_paragraphs_initial and trans_paragraphs >= min_trans_paragraphs and trans_len > orig_len * 0.65:
        print(f"✓ Условия выполнены:")
        print(f"  - {orig_lines} > {orig_paragraphs_initial}")
        print(f"  - {trans_paragraphs} >= {min_trans_paragraphs}")
        print(f"  - {trans_len} > {orig_len * 0.65:.0f}")
        print("→ Устанавливаем para_ratio = 1.0")
        para_ratio = 1.0
    else:
        print(f"✗ Условия НЕ выполнены")
else:
    print(f"✗ Условие НЕ выполнено")

print(f"\nИтоговый para_ratio = {para_ratio:.3f}")

# Финальная проверка
print("\n" + "=" * 60)
print("ФИНАЛЬНАЯ ПРОВЕРКА")
print("=" * 60)

if para_ratio < 0.6:
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: para_ratio {para_ratio:.3f} < 0.6")
    print(f"   Сообщение: Критическая разница в абзацах: {orig_paragraphs} → {trans_paragraphs} ({para_ratio:.1%})")
else:
    print(f"✅ Валидация пройдена: para_ratio {para_ratio:.3f} >= 0.6")