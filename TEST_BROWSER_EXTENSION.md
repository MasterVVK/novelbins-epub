# Тестирование Browser Extension

**Новелла создана!** ID: 11

---

## ✅ Новелла готова к тестированию

### Информация о новелле:

```
ID: 11
Название: Forty Millenniums of Cultivation
Оригинал: 修真四万年
Автор: The Enlightened Master Crouching Cow
URL: https://czbooks.net/n/ul6pe
Тип источника: czbooks
Статус: pending

Cloudflare cookies: ❌ Не установлены (добавьте через Browser Extension)
```

---

## 🚀 Шаги для тестирования

### Шаг 1: Установите Browser Extension (3 минуты)

1. **Откройте Chrome Extensions:**
   ```
   chrome://extensions/
   ```

2. **Включите Developer mode** (переключатель справа сверху)

3. **Нажмите "Load unpacked"** и выберите:
   ```
   /home/user/novelbins-epub/browser_extension/
   ```

4. **Закрепите расширение:**
   - Кликните иконку пазла в панели Chrome
   - Найдите "Novelbins Cookie Extractor"
   - Нажмите булавку (pin)

✅ **Расширение установлено!**

---

### Шаг 2: Получите Cloudflare cookies (5 секунд)

1. **Откройте czbooks.net:**
   ```
   https://czbooks.net
   ```

2. **Дождитесь Cloudflare challenge**
   - Страница покажет "Checking your browser..."
   - Подождите ~5 секунд
   - Страница загрузится нормально

3. **Откройте Browser Extension**
   - Кликните на иконку расширения в панели

4. **Извлеките cookies**
   - Нажмите кнопку: **[🔍 Извлечь Cookies]**
   - Вы увидите:
     ```
     ✅ Успешно! Найдено 12 cookies

     [Cookies preview: cf_clearance=xxx; __cf_bm=yyy; ...]

     [12 Всего cookies] [3 Cloudflare]
     ```

5. **Отправьте в Web App**
   - Нажмите кнопку: **[📤 Отправить в Web App]**
   - Должно появиться:
     ```
     ✅ Cookies успешно отправлены в Web App!
     ```

✅ **Cookies извлечены и отправлены!**

---

### Шаг 3: Обновите новеллу с cookies

**Вариант A: Через форму редактирования (рекомендуется)**

1. Откройте:
   ```
   http://192.168.0.58:5001/edit-novel/11
   ```

2. Найдите поле **"Cookies для обхода Cloudflare"**

3. Вставьте cookies (должны быть уже там, если вы отправили через расширение)

4. Нажмите **"Сохранить изменения"**

**Вариант B: Через новую форму создания**

1. Откройте:
   ```
   http://192.168.0.58:5001/new-novel
   ```

2. Выберите источник: **CZBooks**

3. Инструкция по cookies появится автоматически

4. Cookies должны быть уже вставлены (если отправили через расширение)

5. Заполните остальные поля и создайте новеллу

✅ **Cookies добавлены к новелле!**

---

### Шаг 4: Запустите парсинг (тестирование)

1. **Откройте страницу новеллы:**
   ```
   http://192.168.0.58:5001/novel/11
   ```

2. **Запустите парсинг:**
   - Нажмите кнопку **"Парсить главы"** или аналогичную
   - Или используйте API endpoint

3. **Проверьте результат:**
   - Парсер должен использовать cookies
   - Cloudflare challenge должен быть пройден
   - Главы должны успешно загрузиться

✅ **Парсинг работает с cookies!**

---

## 🔍 Проверка работы

### Проверка 1: Расширение установлено

Откройте `chrome://extensions/` и убедитесь:
```
✓ Novelbins Cookie Extractor
  Version: 1.0.0
  Enabled: Yes
```

---

### Проверка 2: Cookies извлечены

В расширении после клика "Извлечь Cookies":
```
✓ Статус: ✅ Успешно! Найдено 12 cookies
✓ Preview показывает: cf_clearance=xxx; __cf_bm=yyy; ...
✓ Статистика: [12 Всего] [3 Cloudflare]
```

---

### Проверка 3: Cookies отправлены в Web App

После клика "Отправить в Web App":
```
✓ Статус: ✅ Cookies успешно отправлены в Web App!
✓ В браузерной консоли (F12) нет ошибок CORS
✓ Response: {success: true, cookies: "cf_clearance=..."}
```

---

### Проверка 4: Cookies в базе данных

Проверьте через Python:
```python
python3 -c "
import sys
sys.path.insert(0, 'web_app')
from app import create_app, db
from app.models.novel import Novel

app = create_app()
with app.app_context():
    novel = Novel.query.get(11)
    print(f'Auth cookies: {\"✅ Установлены\" if novel.auth_cookies else \"❌ Не установлены\"}')
    print(f'Auth enabled: {novel.auth_enabled}')
    if novel.auth_cookies:
        print(f'Cookies length: {len(novel.auth_cookies)} символов')
        print(f'Contains cf_clearance: {\"cf_clearance\" in novel.auth_cookies}')
"
```

Должен вывести:
```
✓ Auth cookies: ✅ Установлены
✓ Auth enabled: True
✓ Cookies length: 500+ символов
✓ Contains cf_clearance: True
```

---

### Проверка 5: Парсер использует cookies

Проверьте через Python:
```python
python3 -c "
import sys
sys.path.insert(0, 'web_app')
from app import create_app, db
from app.models.novel import Novel
from parsers import create_parser

app = create_app()
with app.app_context():
    novel = Novel.query.get(11)
    parser = create_parser('czbooks', auth_cookies=novel.auth_cookies)

    print('📚 Тестирование парсера с cookies...')
    print(f'Parser type: {type(parser).__name__}')
    print(f'Auth cookies set: {bool(parser.auth_cookies)}')
    print(f'Cookies length: {len(parser.auth_cookies) if parser.auth_cookies else 0}')

    # Попробуйте получить информацию о книге
    try:
        book_info = parser.get_book_info(novel.source_url)
        print('✅ Информация о книге успешно получена!')
        print(f'   Название: {book_info.get(\"title\")}')
        print(f'   Автор: {book_info.get(\"author\")}')
    except Exception as e:
        print(f'❌ Ошибка: {e}')
    finally:
        parser.close()
"
```

---

## 🎯 Ожидаемый результат

После выполнения всех шагов:

1. ✅ Browser Extension установлен и работает
2. ✅ Cookies успешно извлечены с czbooks.net
3. ✅ Cookies отправлены в Web App (192.168.0.58:5001)
4. ✅ Новелла обновлена с cookies
5. ✅ Парсер использует cookies для обхода Cloudflare
6. ✅ Главы успешно парсятся

---

## 📊 Сравнение: До и После

| Действие | Без Browser Extension | С Browser Extension |
|----------|----------------------|---------------------|
| **Открыть DevTools** | ✅ Требуется (F12) | ❌ Не требуется |
| **Найти вкладку Application** | ✅ Требуется | ❌ Не требуется |
| **Найти Cookies** | ✅ Требуется | ❌ Не требуется |
| **Скопировать cookies** | ✅ Вручную | ✅ 1 кнопка |
| **Отформатировать** | ✅ Вручную | ✅ Автоматически |
| **Вставить в форму** | ✅ Требуется | ✅ Автоматически |
| **Время** | ~10 секунд | ~5 секунд |
| **Шагов** | 7 | 2 |
| **Сложность** | Средняя | Простая |

---

## ❗ Устранение неполадок

### Проблема: "0 cookies найдено"

**Причины:**
- Не дождались Cloudflare challenge
- Открыли расширение на другой вкладке

**Решение:**
1. Убедитесь что вы на `czbooks.net`
2. Подождите ~5 секунд после загрузки
3. Попробуйте снова "Извлечь Cookies"

---

### Проблема: "Failed to fetch" при отправке

**Причины:**
- Web App не запущен
- Неверный URL
- CORS ошибка

**Решение:**
1. Проверьте что Web App запущен:
   ```bash
   curl http://192.168.0.58:5001
   ```

2. Проверьте URL в расширении:
   ```
   http://192.168.0.58:5001
   ```

3. Проверьте Console (F12) на ошибки CORS

---

### Проблема: Cookies не сохраняются в новелле

**Причины:**
- Cookies не были отправлены
- API endpoint не работает
- База данных не обновилась

**Решение:**
1. Проверьте ответ API в Console (F12):
   ```javascript
   // Должен быть:
   {success: true, cookies: "cf_clearance=..."}
   ```

2. Проверьте базу данных (см. Проверка 4)

3. Попробуйте вставить cookies вручную через форму

---

### Проблема: Парсинг не работает с cookies

**Причины:**
- Cookies истекли (>24 часа)
- Cookies неправильного формата
- Cloudflare обнаружил автоматизацию

**Решение:**
1. Получите новые cookies (занимает 5 секунд с расширением)
2. Проверьте формат cookies (должен быть: `name1=value1; name2=value2`)
3. Попробуйте non-headless режим парсера

---

## 📖 Дополнительная информация

### Документация:

- **browser_extension/QUICK_START.md** - Быстрый старт расширения
- **browser_extension/INSTALLATION.md** - Подробная установка
- **browser_extension/README.md** - Полная документация
- **BROWSER_EXTENSION_READY.md** - Обзор готового решения
- **CLOUDFLARE_SOLUTION_FINAL.md** - Финальное решение
- **CLOUDFLARE_AUTOMATION_OPTIONS.md** - Все варианты автоматизации

### Полезные ссылки:

```
Web App Dashboard: http://192.168.0.58:5001
Новелла ID 11: http://192.168.0.58:5001/novel/11
Редактирование: http://192.168.0.58:5001/edit-novel/11
Создание новой: http://192.168.0.58:5001/new-novel
Chrome Extensions: chrome://extensions/
CZBooks: https://czbooks.net
```

---

## ✨ Готово к тестированию!

**Новелла создана:** ✅
**Browser Extension готов:** ✅
**Документация готова:** ✅

**Начните тестирование:**
1. Установите расширение (3 мин)
2. Извлеките cookies (5 сек)
3. Запустите парсинг

**Время:** ~10 минут на всё
**Автоматизация:** 95%

---

**Удачи в тестировании! 🎉**

При возникновении проблем см. раздел "Устранение неполадок" выше или документацию в `browser_extension/`.

---

**Создано:** 2025-10-13
**Новелла ID:** 11
**Тип источника:** czbooks
**URL:** https://czbooks.net/n/ul6pe
