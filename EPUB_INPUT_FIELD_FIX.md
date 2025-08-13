# 🔧 Исправление поля ввода для EPUB источников

## 📝 Проблема

При редактировании новеллы с типом источника EPUB браузер показывал сообщение "Введите адрес сайта", потому что поле `source_url` имело тип `type="url"`, который требует валидный URL формат. Для EPUB источников это неправильно, так как там используется путь к файлу.

## ❌ Исходный код (проблемный)

**Файл**: `/web_app/app/templates/edit_novel.html`

```html
<div class="mb-3">
    <label for="source_url" class="form-label">URL источника *</label>
    <input type="url" class="form-control" id="source_url" name="source_url" 
           value="{{ novel.source_url }}" required>
    <div class="form-text">Ссылка на страницу новеллы</div>
</div>
```

❌ **Проблемы**:
- `type="url"` требует URL формат даже для EPUB файлов
- Статичная метка "URL источника" для всех типов
- Статичная подсказка "Ссылка на страницу новеллы"

## ✅ Исправленный код

### 1. Динамические метки и тип поля

```html
<div class="mb-3">
    <label for="source_url" class="form-label" id="source_url_label">
        {% if novel.source_type == 'epub' %}
            Путь к EPUB файлу *
        {% else %}
            URL источника *
        {% endif %}
    </label>
    <input type="{% if novel.source_type == 'epub' %}text{% else %}url{% endif %}" 
           class="form-control" id="source_url" name="source_url" 
           value="{{ novel.source_url }}" required
           placeholder="{% if novel.source_type == 'epub' %}Путь к EPUB файлу{% else %}URL источника{% endif %}">
    <div class="form-text" id="source_url_help">
        {% if novel.source_type == 'epub' %}
            Укажите полный путь к EPUB файлу на сервере
        {% else %}
            Ссылка на страницу новеллы
        {% endif %}
    </div>
</div>
```

### 2. JavaScript для динамического обновления

```javascript
// Динамическое изменение поля source_url в зависимости от типа источника
document.getElementById('source_type').addEventListener('change', function() {
    const sourceType = this.value;
    const sourceUrlInput = document.getElementById('source_url');
    const sourceUrlLabel = document.getElementById('source_url_label');
    const sourceUrlHelp = document.getElementById('source_url_help');
    
    if (sourceType === 'epub') {
        sourceUrlInput.type = 'text';
        sourceUrlInput.placeholder = 'Путь к EPUB файлу';
        sourceUrlLabel.textContent = 'Путь к EPUB файлу *';
        sourceUrlHelp.textContent = 'Укажите полный путь к EPUB файлу на сервере';
    } else {
        sourceUrlInput.type = 'url';
        sourceUrlInput.placeholder = 'URL источника';
        sourceUrlLabel.textContent = 'URL источника *';
        sourceUrlHelp.textContent = 'Ссылка на страницу новеллы';
    }
});
```

## 🎯 Результат

### Для EPUB источников:
- ✅ **Тип поля**: `type="text"` (принимает пути к файлам)
- ✅ **Метка**: "Путь к EPUB файлу *"
- ✅ **Placeholder**: "Путь к EPUB файлу"
- ✅ **Подсказка**: "Укажите полный путь к EPUB файлу на сервере"

### Для других источников:
- ✅ **Тип поля**: `type="url"` (валидация URL)
- ✅ **Метка**: "URL источника *"
- ✅ **Placeholder**: "URL источника"
- ✅ **Подсказка**: "Ссылка на страницу новеллы"

### Динамическое изменение:
- ✅ При смене типа источника интерфейс обновляется автоматически
- ✅ Нет необходимости перезагружать страницу
- ✅ Корректная валидация для каждого типа источника

## 🧪 Тестирование

### Пример валидных данных для EPUB:
- ✅ `/home/user/novelbins-epub/web_app/instance/epub_files/qinkan.net.epub`
- ✅ `/path/to/book.epub`
- ✅ `./books/novel.epub`

### Браузер больше не требует URL формат:
- ❌ До исправления: "Введите адрес сайта"
- ✅ После исправления: Принимает пути к файлам

## 📋 Затронутые файлы

1. `/web_app/app/templates/edit_novel.html` - основной шаблон редактирования
2. `/EPUB_INPUT_FIELD_FIX.md` - документация (этот файл)

## 🚀 Готово к использованию

Теперь при редактировании EPUB новелл:
- Поле корректно принимает пути к файлам
- Интерфейс адаптируется под тип источника
- Нет ложных предупреждений браузера
- Валидация работает корректно

---
**Дата**: 05.08.2025  
**Статус**: ✅ Исправлено и готово к использованию