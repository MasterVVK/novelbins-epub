# 🎉 Версия 1.1.0 - Стабильный релиз!

**Дата:** 2025-10-13 10:52
**Версия:** 1.1.0
**Размер:** 19 KB

---

## ✅ Что исправлено в версии 1.1.0

### 1. Ошибка `chrome.storage.sync` ✅
**Проблема:** `Cannot read properties of undefined (reading 'sync')`
**Решение:** Добавлена проверка доступности API перед использованием

### 2. "Мало кукисов" ✅
**Проблема:** Открывалась главная страница, cookies не успевали загружаться
**Решение:**
- ✅ Автоматическое открытие конкретной страницы новеллы (`https://czbooks.net/n/ul6pe`)
- ✅ Увеличено время ожидания с 10 до 15 секунд
- ✅ Автоматическое определение URL из API Web App

### 3. Поддержка обоих типов source_type ✅
**Проблема:** Новелла имела `source_type: 'czbooks'`, а искали `'czbooks.net'`
**Решение:** Поддержка обоих вариантов: `'czbooks'` и `'czbooks.net'`

### 4. Система версионирования ✅
**Новое:** Автоматическая проверка обновлений при открытии расширения
**Функции:**
- Отображение текущей версии в footer
- Автоматическое уведомление о новых версиях
- Кнопка "Скачать обновление" прямо в popup
- API endpoint `/api/extension/version`

---

## 📥 Установка версии 1.1.0

### Вариант A: Обновление существующего расширения

1. **Удалите старую версию:**
   ```
   chrome://extensions/
   → "Novelbins Cookie Extractor"
   → Удалить
   ```

2. **Скачайте новую версию:**
   ```
   http://192.168.0.58:5001/download-extension
   ```

3. **Распакуйте и установите:**
   ```bash
   tar -xzf browser_extension.tar.gz
   ```
   ```
   chrome://extensions/
   → Developer mode: ON
   → Load unpacked → browser_extension/
   ```

### Вариант B: Первая установка

Следуйте инструкции на странице:
```
http://192.168.0.58:5001/download-extension
```

---

## 🚀 Использование

### Шаг 1: Откройте расширение
Кликните на иконку в панели Chrome

### Шаг 2: Проверьте настройки
- **Web App URL:** `http://192.168.0.58:5001` (должен быть заполнен автоматически)
- **Домен:** `czbooks.net` (выбран по умолчанию)

### Шаг 3: Получите cookies
Нажмите кнопку: **"🚀 Автоматически получить Cookies"**

### Шаг 4: Ждите 15 секунд
Процесс:
```
Открываем czbooks.net в новой вкладке...
→ Ожидание Cloudflare challenge (~15 секунд)...
→ ✅ Успешно! Найдено 10-20 cookies
→ Отправляем cookies в Web App...
→ ✅ Cookies успешно отправлены в Web App!
```

### Шаг 5: Готово!
Cookies автоматически сохранены в новеллу ID 11

---

## 🎁 Новые возможности

### 1. Автоматическая проверка обновлений
При открытии popup расширение:
- Проверяет текущую версию на сервере
- Если доступна новая версия - показывает уведомление
- Предлагает скачать обновление одним кликом

### 2. Отображение версии
В нижней части popup показывается текущая версия: `v1.1.0`

### 3. Умное открытие страниц
Расширение автоматически:
- Запрашивает список новелл из Web App
- Находит новеллу czbooks (поддержка типов `czbooks` и `czbooks.net`)
- Открывает конкретную страницу новеллы вместо главной
- Если API недоступен - использует главную страницу

### 4. Улучшенные сообщения
Теперь показывается количество найденных cookies:
- `⚠️ Найдено мало cookies (3). Попробуйте еще раз.`
- `✅ Успешно! Найдено 12 cookies`

---

## 📊 Технические детали

### Что происходит внутри:

1. **Определение URL:**
   ```javascript
   GET http://192.168.0.58:5001/api/novels?active_only=true
   → Поиск новеллы с source_type == 'czbooks' || 'czbooks.net'
   → Получение source_url: https://czbooks.net/n/ul6pe
   ```

2. **Открытие страницы:**
   ```javascript
   chrome.tabs.create({
     url: 'https://czbooks.net/n/ul6pe',
     active: false  // В фоне!
   })
   ```

3. **Ожидание:**
   ```javascript
   await new Promise(resolve => setTimeout(resolve, 15000));
   ```

4. **Извлечение cookies:**
   ```javascript
   chrome.cookies.getAll({ domain: 'czbooks.net' })
   → Результат: 10-20 cookies (включая cf_clearance)
   ```

5. **Поиск новеллы:**
   ```javascript
   GET /api/novels?active_only=true
   → Поиск по source_type: 'czbooks' или 'czbooks.net'
   → Получение novel_id: 11
   ```

6. **Отправка:**
   ```javascript
   POST /api/cloudflare-auth/save-cookies
   Body: {
     cookies: "cf_clearance=...; __cf_bm=...",
     novel_id: 11,
     source: "browser_extension"
   }
   ```

7. **Проверка обновлений:**
   ```javascript
   GET /api/extension/version
   → Response: { version: "1.1.0", changelog: [...] }
   → Сравнение с CURRENT_VERSION
   → Если новее - показать уведомление
   ```

---

## ✅ Проверка результата

### В расширении:
После нажатия кнопки вы увидите:

```
Статус: ✅ Успешно! Найдено 12 cookies
Отправляем cookies в Web App...
Статус: ✅ Cookies успешно отправлены в Web App!

Preview: cf_clearance=xxx; __cf_bm=yyy; _cfuvid=zzz; ...

Статистика:
12 Всего cookies
3 Cloudflare
```

### На сервере:
```bash
python3 -c "
import sys
sys.path.insert(0, 'web_app')
from app import create_app, db
from app.models.novel import Novel

app = create_app()
with app.app_context():
    novel = Novel.query.get(11)
    if novel and novel.auth_cookies:
        print(f'✅ SUCCESS!')
        print(f'Novel: {novel.title}')
        print(f'URL: {novel.source_url}')
        print(f'Cookies: {len(novel.auth_cookies)} символов')
        print(f'cf_clearance: {\"cf_clearance\" in novel.auth_cookies}')
    else:
        print('❌ Нет cookies')
"
```

Ожидаемый результат:
```
✅ SUCCESS!
Novel: Forty Millenniums of Cultivation
URL: https://czbooks.net/n/ul6pe
Cookies: 500+ символов
cf_clearance: True
```

---

## ❓ FAQ

### Почему "Найдено мало cookies"?
Возможные причины:
1. Cloudflare challenge еще не пройден (попробуйте еще раз)
2. Страница не успела загрузиться (увеличено до 15 сек в v1.1.0)
3. Нет подключения к czbooks.net

**Решение:** Просто нажмите кнопку еще раз!

### Как обновиться до 1.1.0?
1. Удалите старую версию в `chrome://extensions/`
2. Скачайте новую с http://192.168.0.58:5001/download-extension
3. Установите как обычно

### Как работает автоматическое обновление?
- При открытии popup расширение проверяет версию на сервере
- Если доступна новая версия - появляется уведомление
- Нажмите "Скачать обновление" → откроется страница загрузки
- Удалите старую версию и установите новую

### Нужно ли качать заново при каждом обновлении?
Да, Chrome Extensions требует ручной переустановки для unpacked extensions.
Но теперь вы будете знать о новых версиях автоматически!

---

## 📋 Changelog

### v1.1.0 (2025-10-13)
- ✅ Исправлена ошибка `chrome.storage.sync`
- ✅ Увеличено время ожидания до 15 секунд
- ✅ Автоматическое открытие конкретной страницы новеллы
- ✅ Поддержка source_type: 'czbooks' и 'czbooks.net'
- ✅ Система версионирования и проверка обновлений
- ✅ Отображение версии в popup
- ✅ API endpoint `/api/extension/version`
- ✅ Улучшенные сообщения об ошибках

### v1.0.0 (2025-10-13)
- Первая версия с автоматическим извлечением cookies
- Открытие czbooks.net в фоновой вкладке
- Автоматическая отправка в Web App
- Автоматическое определение новеллы

---

## 🔗 Ссылки

- **Скачать:** http://192.168.0.58:5001/download-extension
- **Новелла:** http://192.168.0.58:5001/novel/11
- **API версии:** http://192.168.0.58:5001/api/extension/version
- **Главная:** http://192.168.0.58:5001

---

## 🎉 Готово!

**Скачайте версию 1.1.0:**
```
http://192.168.0.58:5001/download-extension
```

**Все проблемы исправлены! Удачи! 🚀**

---

**Версия:** 1.1.0
**Размер:** 19 KB
**Создано:** 2025-10-13 10:52
**Web App:** http://192.168.0.58:5001
