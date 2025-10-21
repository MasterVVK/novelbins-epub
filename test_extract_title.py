#!/usr/bin/env python3
"""
Тестирование исправленной функции extract_title_and_content
"""
import sys
sys.path.insert(0, '/home/user/novelbins-epub/web_app')

from app import create_app
from app.services.translator_service import TranslatorService

# Создаем приложение и контекст
app = create_app()

with app.app_context():
    # Создаем сервис переводчика
    service = TranslatorService()

    # Читаем старый правильный перевод (где есть начало)
    with open('/home/user/novelbins-epub/5-gemini-2.5-flash.txt', 'r', encoding='utf-8') as f:
        correct_translation = f.read()

    # Читаем новый обрезанный перевод (где нет начала)
    with open('/home/user/novelbins-epub/5-gemini-2.5-flash-new.txt', 'r', encoding='utf-8') as f:
        truncated_translation = f.read()

    print("=" * 80)
    print("ТЕСТИРОВАНИЕ ПРАВИЛЬНОГО ПЕРЕВОДА (с началом)")
    print("=" * 80)

    title1, content1 = service.extract_title_and_content(correct_translation)

    print(f"\nИзвлеченный заголовок: '{title1}'")
    print(f"Длина контента: {len(content1)} символов")
    print(f"\nПервые 200 символов контента:")
    print(content1[:200])

    # Проверяем, что начало сохранилось
    expected_start = "Как только деревянный меч упал в котёл"
    if expected_start in content1[:100]:
        print(f"\n✅ УСПЕХ! Начало текста сохранилось: '{expected_start}'")
    else:
        print(f"\n❌ ОШИБКА! Начало текста потеряно!")
        print(f"Ожидалось: '{expected_start}'")
        print(f"Получено: '{content1[:100]}'")

    print("\n" + "=" * 80)
    print("ТЕСТИРОВАНИЕ ОБРЕЗАННОГО ПЕРЕВОДА (без начала)")
    print("=" * 80)

    title2, content2 = service.extract_title_and_content(truncated_translation)

    print(f"\nИзвлеченный заголовок: '{title2}'")
    print(f"Длина контента: {len(content2)} символов")
    print(f"\nПервые 200 символов контента:")
    print(content2[:200])

    # Это уже обрезанный текст, но функция не должна его обрезать еще больше
    first_line = truncated_translation.split('\n')[0]
    print(f"\nПервая строка оригинала: '{first_line[:100]}'")
    print(f"Первая строка контента:  '{content2[:100]}'")

    if content2.startswith(first_line):
        print(f"\n✅ УСПЕХ! Первая строка НЕ была отброшена как заголовок")
    else:
        print(f"\n❌ ОШИБКА! Первая строка была неправильно отброшена!")

    print("\n" + "=" * 80)
    print("ТЕСТИРОВАНИЕ С РЕАЛЬНЫМ ЗАГОЛОВКОМ")
    print("=" * 80)

    # Проверяем, что функция правильно определяет настоящий заголовок
    test_with_title = "Глава 5: Испытание огнем\n\nКак только деревянный меч упал в котёл, ничего особенного не произошло."

    title3, content3 = service.extract_title_and_content(test_with_title)

    print(f"\nИзвлеченный заголовок: '{title3}'")
    print(f"Контент начинается с: '{content3[:50]}'")

    if title3 == "Глава 5: Испытание огнем" and content3.startswith("Как только"):
        print(f"\n✅ УСПЕХ! Настоящий заголовок правильно определен и извлечен")
    else:
        print(f"\n❌ ОШИБКА! Настоящий заголовок не был правильно обработан")
        print(f"Ожидался заголовок: 'Глава 5: Испытание огнем'")
        print(f"Получен заголовок: '{title3}'")
