#!/usr/bin/env python3
"""
Тестовая версия скрипта - обрабатывает только первые N глав
"""
import sys
sys.path.insert(0, '/home/user/novelbins-epub')
exec(open('fix_missing_titles.py').read().replace(
    'translations = query.filter(',
    'translations = query.filter('
).replace(
    ').all()',
    ').limit(5).all()  # ← ОГРАНИЧЕНИЕ НА 5 ГЛАВ ДЛЯ ТЕСТА'
))
