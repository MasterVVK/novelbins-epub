# 🔧 Исправление проверки URL для EPUB источников

## 📝 Проблема

При сохранении новелл с типом источника EPUB система выполняла проверку URL, которая была предназначена для веб-URL, но не подходила для путей к файлам EPUB.

## ✅ Решение

### 1. Обновлен `ParserIntegrationService.validate_url_for_source()`

**Файл**: `/web_app/app/services/parser_integration.py`

```python
@classmethod
def validate_url_for_source(cls, url: str, expected_source: str) -> bool:
    # Специальная обработка для EPUB источников
    if expected_source == 'epub':
        # Проверяем, что это путь к EPUB файлу
        return (url.lower().endswith('.epub') or 
               'epub_files' in url or 
               url.lower().endswith('.epub/'))
    
    detected = cls.detect_source_from_url(url)
    return detected == expected_source
```

### 2. Улучшены паттерны URL в `ParserFactory`

**Файл**: `/parsers/parser_factory.py`

```python
_url_patterns: Dict[str, str] = {
    r'qidian\.com': 'qidian',
    r'm\.qidian\.com': 'qidian', 
    r'book\.qidian\.com': 'qidian',
    r'\.epub(?:/.*)?$': 'epub',  # Файлы EPUB (включая пути с дополнительными слешами)
    r'epub_files': 'epub',  # Директория с EPUB файлами
}
```

### 3. Добавлена проверка в создание новелл

**Файл**: `/web_app/app/views.py` - функция `add_novel()`

```python
# Проверка соответствия URL и источника
if source_url and not ParserIntegrationService.validate_url_for_source(source_url, source_type):
    detected = ParserIntegrationService.detect_source_from_url(source_url)
    if detected and detected != source_type:
        if source_type == 'epub':
            flash(f'Предупреждение: Путь к файлу не похож на EPUB файл. Убедитесь, что указан правильный путь.', 'warning')
        else:
            flash(f'Внимание: URL больше подходит для источника "{detected}", но выбран "{source_type}"', 'warning')
```

### 4. Добавлена проверка в редактирование новелл

**Файл**: `/web_app/app/views.py` - функция `edit_novel()`

Добавлена аналогичная проверка + обновление поля `epub_file_path`:

```python
# Для EPUB источников обновляем также epub_file_path
if source_type == 'epub':
    novel.epub_file_path = source_url

# Проверяем соответствие URL/пути и типа источника
if source_url and not ParserIntegrationService.validate_url_for_source(source_url, source_type):
    # ... проверка и предупреждения
```

## 🧪 Тестирование

Создан тест-скрипт `test_epub_validation.py` для проверки работы:

### Валидные EPUB пути:
- ✅ `/path/to/book.epub`
- ✅ `/epub_files/novel.epub`
- ✅ `/home/user/novelbins-epub/web_app/instance/epub_files/qinkan.net.epub`

### Невалидные пути:
- ❌ `/home/user/document.pdf`
- ❌ `https://qidian.com/book/123` (для EPUB)
- ❌ `/home/user/text.txt`

## 🎯 Результат

### До исправления:
- ❌ EPUB пути валидировались как веб-URL
- ❌ Некорректные предупреждения при сохранении
- ❌ Путаница между URL и путями к файлам

### После исправления:
- ✅ EPUB пути корректно распознаются
- ✅ Правильные предупреждения для разных типов источников
- ✅ Автоматическое обновление `epub_file_path`
- ✅ Улучшенная валидация путей

## 📋 Затронутые файлы

1. `/web_app/app/services/parser_integration.py` - основная логика валидации
2. `/parsers/parser_factory.py` - паттерны для определения источников  
3. `/web_app/app/views.py` - проверка при создании/редактировании новелл
4. `/test_epub_validation.py` - тест-скрипт (новый)

## 🚀 Готово к использованию

Теперь система корректно обрабатывает EPUB источники:
- При создании новой новеллы
- При редактировании существующей новеллы
- При автоматическом определении типа источника
- При валидации путей к файлам

---
**Дата**: 05.08.2025  
**Статус**: ✅ Исправлено и протестировано