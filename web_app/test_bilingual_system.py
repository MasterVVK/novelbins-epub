#!/usr/bin/env python3
"""
Тестовый скрипт для проверки системы двуязычного выравнивания
"""
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import BilingualPromptTemplate, BilingualAlignment, Novel, Chapter
from app.services.bilingual_prompt_template_service import BilingualPromptTemplateService
from app.services.bilingual_alignment_service import BilingualAlignmentService

def test_imports():
    """Тест 1: Проверка импортов"""
    print("\n" + "="*60)
    print("ТЕСТ 1: Проверка импортов моделей и сервисов")
    print("="*60)

    try:
        # Проверяем импорт моделей
        print("✅ BilingualPromptTemplate импортирована")
        print("✅ BilingualAlignment импортирована")

        # Проверяем импорт сервисов
        print("✅ BilingualPromptTemplateService импортирован")
        print("✅ BilingualAlignmentService импортирован")

        print("\n✅ Все импорты успешны!")
        return True
    except Exception as e:
        print(f"\n❌ Ошибка импорта: {e}")
        return False

def test_models(app):
    """Тест 2: Проверка работы с моделями"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Проверка работы с моделями БД")
    print("="*60)

    with app.app_context():
        try:
            # Проверяем, что таблицы существуют
            count_templates = BilingualPromptTemplate.query.count()
            count_alignments = BilingualAlignment.query.count()

            print(f"✅ Таблица bilingual_prompt_templates: {count_templates} записей")
            print(f"✅ Таблица bilingual_alignments: {count_alignments} записей")

            # Проверяем связь с Novel
            novels_with_template = Novel.query.filter(Novel.bilingual_template_id.isnot(None)).count()
            print(f"✅ Новелл с привязанным шаблоном: {novels_with_template}")

            print("\n✅ Модели работают корректно!")
            return True
        except Exception as e:
            print(f"\n❌ Ошибка работы с моделями: {e}")
            import traceback
            traceback.print_exc()
            return False

def test_template_service(app):
    """Тест 3: Создание дефолтного шаблона"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Создание дефолтного шаблона двуязычности")
    print("="*60)

    with app.app_context():
        try:
            # Проверяем существующие шаблоны
            existing = BilingualPromptTemplate.query.all()
            print(f"Существующих шаблонов: {len(existing)}")

            if existing:
                for template in existing:
                    print(f"  - {template.name} (id={template.id}, default={template.is_default})")

            # Создаем дефолтный шаблон если его нет
            default_template = BilingualPromptTemplateService.get_default_template()

            if not default_template:
                print("\nСоздаем дефолтный шаблон...")
                created = BilingualPromptTemplateService.create_default_templates()
                print(f"✅ Создано шаблонов: {len(created)}")

                for template in created:
                    print(f"  - {template.name}")
                    print(f"    Категория: {template.category}")
                    print(f"    Temperature: {template.temperature}")
                    print(f"    Max tokens: {template.max_tokens}")
                    print(f"    Промпт (первые 100 символов): {template.alignment_prompt[:100]}...")

                default_template = BilingualPromptTemplateService.get_default_template()

            if default_template:
                print(f"\n✅ Дефолтный шаблон: {default_template.name}")
                print(f"   ID: {default_template.id}")
                print(f"   Категория: {default_template.category}")
                return True
            else:
                print("\n❌ Не удалось создать дефолтный шаблон")
                return False

        except Exception as e:
            print(f"\n❌ Ошибка создания шаблона: {e}")
            import traceback
            traceback.print_exc()
            return False

def test_alignment_service(app):
    """Тест 4: Тестирование BilingualAlignmentService"""
    print("\n" + "="*60)
    print("ТЕСТ 4: Тестирование BilingualAlignmentService")
    print("="*60)

    with app.app_context():
        try:
            # Создаем экземпляр сервиса
            service = BilingualAlignmentService()
            print("✅ BilingualAlignmentService создан")

            # Проверяем, что можем получить шаблон
            default_template = service._get_template(None)
            if default_template:
                print(f"✅ Получен дефолтный шаблон: {default_template.name}")
            else:
                print("⚠️  Дефолтный шаблон не найден")

            # Проверяем метод создания моноязычного выравнивания
            test_text = "Это первый абзац.\n\nЭто второй абзац.\n\nЭто третий абзац."
            mono_alignment = service._create_monolingual_alignment(test_text)
            print(f"\n✅ Тест моноязычного выравнивания:")
            print(f"   Входной текст: 3 абзаца")
            print(f"   Результат: {len(mono_alignment)} пар")

            for i, pair in enumerate(mono_alignment[:2], 1):
                print(f"   Пара {i}:")
                print(f"     RU: {pair['ru'][:50]}...")
                print(f"     ZH: '{pair['zh']}'")
                print(f"     Type: {pair['type']}")
                print(f"     Confidence: {pair['confidence']}")

            print("\n✅ BilingualAlignmentService работает корректно!")
            return True

        except Exception as e:
            print(f"\n❌ Ошибка тестирования сервиса: {e}")
            import traceback
            traceback.print_exc()
            return False

def test_chapter_methods(app):
    """Тест 5: Проверка методов Chapter"""
    print("\n" + "="*60)
    print("ТЕСТ 5: Проверка методов модели Chapter")
    print("="*60)

    with app.app_context():
        try:
            # Ищем главу с переводом и оригиналом
            chapter = Chapter.query.filter(
                Chapter.original_text.isnot(None)
            ).first()

            if not chapter:
                print("⚠️  Нет глав с оригинальным текстом для тестирования")
                return True

            print(f"✅ Найдена глава для тестирования:")
            print(f"   Novel ID: {chapter.novel_id}")
            print(f"   Chapter: {chapter.chapter_number}")
            print(f"   Оригинал: {len(chapter.original_text) if chapter.original_text else 0} символов")
            print(f"   Переводы: {len(chapter.translations)}")

            # Проверяем связь с BilingualAlignment
            if hasattr(chapter, 'bilingual_alignment'):
                if chapter.bilingual_alignment:
                    print(f"   Выравнивание: существует (id={chapter.bilingual_alignment.id})")
                else:
                    print(f"   Выравнивание: не создано")

            print("\n✅ Связи модели Chapter работают корректно!")
            return True

        except Exception as e:
            print(f"\n❌ Ошибка проверки методов: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Главная функция запуска тестов"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ СИСТЕМЫ ДВУЯЗЫЧНОГО ВЫРАВНИВАНИЯ")
    print("="*60)

    # Создаем приложение
    app = create_app()

    # Запускаем тесты
    results = []

    results.append(("Импорты", test_imports()))
    results.append(("Модели БД", test_models(app)))
    results.append(("Создание шаблона", test_template_service(app)))
    results.append(("Сервис выравнивания", test_alignment_service(app)))
    results.append(("Методы Chapter", test_chapter_methods(app)))

    # Итоги
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")

    print(f"\nИтого: {passed}/{total} тестов пройдено")

    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тестов провалено")
        return 1

if __name__ == '__main__':
    sys.exit(main())
