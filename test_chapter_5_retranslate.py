#!/usr/bin/env python3
"""
Симуляция обработки перевода главы 5 с исправленной функцией
"""
import sys
sys.path.insert(0, '/home/user/novelbins-epub/web_app')

from app import create_app, db
from app.services.translator_service import TranslatorService
from app.models import Chapter, Translation

# Создаем приложение и контекст
app = create_app()

with app.app_context():
    # Получаем главу 5 из базы (novel 11, chapter 5)
    chapter = db.session.query(Chapter).filter_by(novel_id=11, chapter_number=5).first()

    if not chapter:
        print("❌ Глава 5 не найдена в базе данных")
        sys.exit(1)

    print(f"✅ Найдена глава: {chapter.original_title} (ID: {chapter.id})")
    print(f"   Оригинальный текст: {len(chapter.original_text)} символов")

    # Получаем текущий перевод
    current_translation = db.session.query(Translation).filter_by(
        chapter_id=chapter.id
    ).order_by(Translation.id.desc()).first()

    if current_translation:
        print(f"\n📝 Текущий перевод в базе:")
        print(f"   Заголовок: '{current_translation.translated_title}'")
        print(f"   Текст: {len(current_translation.translated_text)} символов")
        print(f"   Начало: '{current_translation.translated_text[:100]}'")

        # Проверяем, обрезан ли он
        if "Это дерево" in current_translation.translated_text[:200] or "Эта древесина" in current_translation.translated_text[:200]:
            print(f"\n⚠️  ОБНАРУЖЕНА ПРОБЛЕМА: Текущий перевод начинается с 'Это дерево/Эта древесина'")
            print(f"   Это означает, что начало было обрезано!")
        else:
            print(f"\n✅ Текущий перевод выглядит нормально")
    else:
        print(f"\n⚠️  Перевод не найден в базе")

    # Читаем правильный перевод из файла (тот, что с промпт истории)
    print(f"\n" + "=" * 80)
    print("СИМУЛЯЦИЯ ОБРАБОТКИ С ИСПРАВЛЕННОЙ ФУНКЦИЕЙ")
    print("=" * 80)

    # Используем текст из промпт истории (который был правильным)
    with open('/home/user/novelbins-epub/5-gemini-2.5-flash.txt', 'r', encoding='utf-8') as f:
        llm_response = f.read()

    print(f"\nLLM вернул перевод: {len(llm_response)} символов")
    print(f"Начало ответа LLM: '{llm_response[:100]}'")

    # Создаем сервис и применяем исправленную функцию
    service = TranslatorService()

    title, content = service.extract_title_and_content(llm_response)

    print(f"\n🔍 После extract_title_and_content:")
    print(f"   Извлеченный заголовок: '{title}'")
    print(f"   Длина контента: {len(content)} символов")
    print(f"   Начало контента: '{content[:100]}'")

    # Проверяем, сохранилось ли начало
    expected_start = "Как только деревянный меч"
    if expected_start in content[:50]:
        print(f"\n✅ УСПЕХ! Начало текста сохранилось после обработки!")
        print(f"   Ожидалось: '{expected_start}'")
        print(f"   Получено: '{content[:50]}'")
    else:
        print(f"\n❌ ОШИБКА! Начало текста потеряно!")
        print(f"   Ожидалось: '{expected_start}'")
        print(f"   Получено: '{content[:50]}'")

    print(f"\n" + "=" * 80)
    print("СРАВНЕНИЕ")
    print("=" * 80)

    if current_translation:
        print(f"\nДО исправления (текущий перевод в БД):")
        print(f"  Длина: {len(current_translation.translated_text)} символов")
        print(f"  Начало: '{current_translation.translated_text[:100]}'")

    print(f"\nПОСЛЕ исправления (с новой функцией):")
    print(f"  Длина: {len(content)} символов")
    print(f"  Начало: '{content[:100]}'")

    if current_translation:
        diff = len(content) - len(current_translation.translated_text)
        print(f"\nРазница: {diff} символов")
        if diff > 0:
            print(f"✅ Новый перевод ДЛИННЕЕ на {diff} символов (восстановлено начало)")
        elif diff < 0:
            print(f"⚠️  Новый перевод КОРОЧЕ на {abs(diff)} символов")
        else:
            print(f"➖ Длина одинаковая")
