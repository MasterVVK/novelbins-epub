#!/usr/bin/env python3
"""
Тестирование исправления функции split_long_text
"""
import sys
sys.path.insert(0, '/home/user/novelbins-epub/web_app')

from app import create_app
from app.services.translator_service import TranslatorService

# Создаем приложение и контекст
app = create_app()

with app.app_context():
    # Читаем оригинальный текст
    with open('/home/user/novelbins-epub/5.txt', 'r', encoding='utf-8') as f:
        original_text = f.read()

    print(f"Оригинальный текст, длина: {len(original_text)} символов")
    print(f"Первые 200 символов оригинала:")
    print(original_text[:200])
    print("\n" + "=" * 80 + "\n")

    # Создаем сервис переводчика
    service = TranslatorService()

    # Предобрабатываем текст (как делается в translate_chapter)
    preprocessed_text = service.preprocess_text(original_text)

    print(f"Предобработанный текст, длина: {len(preprocessed_text)} символов")
    print(f"Первые 200 символов после предобработки:")
    print(preprocessed_text[:200])
    print("\n" + "=" * 80 + "\n")

    # Разбиваем на части
    text_parts = service.split_long_text(preprocessed_text)

    print(f"Текст разбит на {len(text_parts)} частей")
    print("\n" + "=" * 80 + "\n")

    # Проверяем первую часть
    print(f"ПЕРВАЯ ЧАСТЬ (длина: {len(text_parts[0])} символов):")
    print(text_parts[0][:500])
    print("\n" + "=" * 80 + "\n")

    # Проверяем, что первая часть начинается с правильного текста
    expected_start = "那木劍一落入鍋內"
    if text_parts[0].startswith(expected_start):
        print("✅ УСПЕХ! Первая часть начинается с правильного текста:")
        print(f"   Ожидалось: {expected_start}")
        print(f"   Получено:  {text_parts[0][:len(expected_start)]}")
    else:
        print("❌ ОШИБКА! Первая часть НЕ начинается с правильного текста:")
        print(f"   Ожидалось: {expected_start}")
        print(f"   Получено:  {text_parts[0][:len(expected_start)]}")

    print("\n" + "=" * 80 + "\n")

    # Проверяем, что весь текст сохранился
    combined_text = ''.join(text_parts)

    if combined_text == preprocessed_text:
        print("✅ УСПЕХ! Весь текст сохранился после разбиения")
    else:
        print("❌ ОШИБКА! Текст был изменен при разбиении")
        print(f"   Оригинал:  {len(preprocessed_text)} символов")
        print(f"   После:     {len(combined_text)} символов")
        print(f"   Разница:   {len(preprocessed_text) - len(combined_text)} символов")
