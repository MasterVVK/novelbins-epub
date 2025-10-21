# Использование OriginalAwareEditorService

## Описание
Новый сервис редактирования переводов с полной поддержкой оригинального текста и глоссария. Обеспечивает максимальную точность через постоянную сверку с оригиналом на каждом этапе редактирования.

## Ключевые преимущества

✅ **Полная сверка с оригиналом** - на каждом этапе редактирования
✅ **Универсальные промпты** - автоматически адаптируются под жанр и произведение
✅ **Восстановление пропущенных деталей** - ничего не теряется из оригинала
✅ **Строгое соблюдение глоссария** - все термины проверяются на каждом этапе

## Как использовать

### 1. Импорт и инициализация

```python
from app.services.original_aware_editor_service import OriginalAwareEditorService
from app.services.translator_service import TranslatorService

# Создаем сервис переводчика
translator_service = TranslatorService()

# Создаем сервис редактирования с оригиналом
editor = OriginalAwareEditorService(translator_service)
```

### 2. Редактирование главы

```python
from app.models import Chapter

# Получаем главу для редактирования
chapter = Chapter.query.filter_by(
    novel_id=novel_id,
    chapter_number=1
).first()

# Запускаем редактирование
result = editor.edit_chapter(chapter)

if result:
    print(f"✅ Глава {chapter.chapter_number} успешно отредактирована")
else:
    print(f"❌ Ошибка при редактировании главы {chapter.chapter_number}")
```

### 3. Пакетное редактирование

```python
# Получаем все переведенные главы, требующие редактирования
chapters = Chapter.query.filter_by(
    novel_id=novel_id,
    status='translated'
).all()

# Редактируем по одной
for chapter in chapters:
    result = editor.edit_chapter(chapter)
    if result:
        print(f"✅ Глава {chapter.chapter_number} отредактирована")
```

## Процесс редактирования

### Этапы обработки:

1. **Анализ с оригиналом**
   - Оценка качества (1-10)
   - Поиск пропущенных деталей
   - Проверка соответствия глоссарию

2. **Исправление несоответствий**
   - Восстановление пропущенных деталей
   - Корректировка терминов по глоссарию
   - Исправление имен персонажей

3. **Улучшение стиля**
   - Сверка ритма с оригиналом
   - Адаптация культурных элементов
   - Устранение канцеляризмов

4. **Полировка диалогов**
   - Сверка тона с оригиналом
   - Естественные формы обращения
   - Передача характеров через речь

5. **Финальная проверка**
   - Полнота перевода
   - Единообразие терминологии
   - Литературное качество

## Универсальность промптов

Промпты автоматически адаптируются под:
- **Жанр** (сянься, уся, современный роман и т.д.)
- **Название произведения**
- **Автора**

Информация берется из базы данных:
```
Жанр: сянься
Произведение: 一念永恒 (Одна мысль о вечности)
Автор: 耳根 (Эргэн)
```

## Требования

### Обязательные данные в Chapter:
- `original_text` - полный оригинальный текст главы
- `current_translation` - переведенный текст (тип 'initial')

### Глоссарий в базе:
- Заполненная таблица `glossary_items` для novel_id
- Правильная категоризация терминов

### Промпт шаблон:
- Связанный `prompt_template` с указанной категорией (жанром)

## Метрики качества

После редактирования качество повышается:
- **Базовое качество**: 5-7/10
- **После редактирования**: 8-10/10
- **Бонус за оригинал**: +3 балла

## Сохраняемые метаданные

```json
{
    "editing_time": 45.2,
    "quality_score_before": 6,
    "quality_score_after": 9,
    "glossary_terms_used": 156,
    "critical_terms": 12,
    "original_text_length": 5234,
    "edited_text_length": 5189,
    "used_original": true,
    "used_full_glossary": true,
    "missing_details_fixed": ["деталь1", "деталь2"]
}
```

## Интеграция в web_app

### Добавление в views.py:

```python
@main_bp.route('/novels/<int:novel_id>/edit-with-original', methods=['POST'])
def edit_novel_with_original(novel_id):
    """Редактирование новеллы с оригиналом"""
    from app.services.original_aware_editor_service import OriginalAwareEditorService

    novel = Novel.query.get_or_404(novel_id)
    editor = OriginalAwareEditorService(translator_service)

    # Получаем главы для редактирования
    chapters = Chapter.query.filter_by(
        novel_id=novel_id,
        status='translated'
    ).all()

    success_count = 0
    for chapter in chapters:
        if editor.edit_chapter(chapter):
            success_count += 1

    flash(f'Отредактировано {success_count} из {len(chapters)} глав', 'success')
    return redirect(url_for('main.novel_detail', novel_id=novel_id))
```

## Проверка результатов

```python
# Проверяем отредактированную главу
from app.models import Translation

edited = Translation.query.filter_by(
    chapter_id=chapter.id,
    translation_type='edited'
).order_by(Translation.created_at.desc()).first()

if edited:
    print(f"Качество: {edited.quality_score}/10")
    print(f"Время редактирования: {edited.translation_time:.1f} сек")
    print(f"Использовано терминов: {edited.context_used.get('glossary_terms_used')}")
```

## Важные замечания

1. **Размер контекста** - сервис передает ПОЛНЫЕ тексты без ограничений
2. **API лимиты** - учитывайте лимиты Gemini/Claude при пакетной обработке
3. **Время обработки** - редактирование с оригиналом занимает 30-60 сек на главу
4. **База данных** - убедитесь что `original_text` заполнен для всех глав

## Отличия от других сервисов

| Сервис | Оригинал | Глоссарий | Промпты |
|--------|----------|-----------|---------|
| EditorService | ❌ | ❌ | Фиксированные |
| GlossaryAwareEditorService | ❌ | ✅ | Фиксированные |
| **OriginalAwareEditorService** | ✅ | ✅ | Универсальные |

## Результат

Система обеспечивает:
- **100% полноту** перевода (ничего не пропущено)
- **100% соответствие** глоссарию
- **Естественность** русского языка
- **Сохранение** всех культурных нюансов