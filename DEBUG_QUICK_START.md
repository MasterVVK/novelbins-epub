# 🔍 Быстрая отладка расширения

## Обновлено: 2025-10-13 11:27
**Добавлено подробное логирование!**

---

## 🚀 Шаг 1: Обновите расширение

**Скачайте новую версию с логированием:**
```
http://192.168.0.58:5001/download-extension
```

**Удалите старую и установите новую:**
```
chrome://extensions/
→ Удалить старую версию
→ Load unpacked → browser_extension/
```

---

## 🔍 Шаг 2: Откройте консоль

### Консоль Popup:
```
1. Кликните на иконку расширения (откроется popup)
2. Правый клик в любом месте popup
3. "Inspect" (Проверить элемент)
4. Откроется DevTools
5. Вкладка "Console"
```

### Консоль Background:
```
chrome://extensions/
→ Найдите "Novelbins Cookie Extractor"
→ Нажмите "Inspect views: service worker"
→ Вкладка "Console"
```

**Держите ОБЕ консоли открытыми!**

---

## 🎯 Шаг 3: Запустите извлечение

В popup нажмите: **"🚀 Автоматически получить Cookies"**

---

## 📊 Шаг 4: Смотрите логи

### В Popup Console вы увидите:

```
🔍 DEBUG: Начинаем автоматическое извлечение cookies
📍 Domain: czbooks.net
🌐 Web App URL: http://192.168.0.58:5001

📡 Запрашиваем список новелл...
📡 Response status: 200
📚 Получено новелл: 1

✅ Найдена новелла: {id: 11, title: "...", source_url: "https://czbooks.net/n/ul6pe"}
🎯 Открываем конкретную новеллу: https://czbooks.net/n/ul6pe

📂 Открываем вкладку: https://czbooks.net/n/ul6pe
✅ Вкладка открыта, ID: 12345

⏳ Ждем 15 секунд...
✅ Ожидание завершено

🍪 Запрашиваем cookies для домена: czbooks.net
🍪 Response: {success: true, cookies: {...}}

📊 Статистика cookies:
  - Всего: 12
  - Cloudflare: 3
  - cf_clearance: ✅
  - __cf_bm: ✅

🗑️ Закрываем вкладку: 12345
📤 Отправляем cookies в Web App...
```

### В Background Console:

```
🍪 [Background] Извлекаем cookies для домена: czbooks.net
🍪 [Background] Получено cookies: 12
🔐 [Background] Cloudflare cookies: 3
  - cf_clearance: xxx...
  - __cf_bm: yyy...
  - _cfuvid: zzz...
📝 [Background] Cookie string length: 500
```

---

## ❌ Что делать если ошибки:

### Ошибка 1: "📡 Response status: 0" или "Failed to fetch"

**Проблема:** Web App недоступен

**Решение:**
```bash
# На сервере проверьте:
curl http://192.168.0.58:5001/api/novels
```

### Ошибка 2: "⚠️ Новелла czbooks не найдена"

**Проблема:** Новелла не создана или не активна

**Решение:**
```bash
python3 -c "
import sys
sys.path.insert(0, 'web_app')
from app import create_app, db
from app.models.novel import Novel

app = create_app()
with app.app_context():
    novel = Novel.query.get(11)
    print('Найдена:', novel.title if novel else 'НЕТ')
    print('Active:', novel.is_active if novel else 'НЕТ')
    print('Source Type:', novel.source_type if novel else 'НЕТ')
"
```

### Ошибка 3: "🍪 [Background] Получено cookies: 0"

**Проблема:** Cloudflare challenge не пройден

**Решение:**
1. Откройте вкладку вручную: https://czbooks.net/n/ul6pe
2. Дождитесь полной загрузки (~10 сек)
3. F12 → Console → `document.cookie`
4. Если пусто - проблема с IP/VPN

### Ошибка 4: "🍪 [Background] Получено cookies: 3, Cloudflare: 0"

**Проблема:** Cookies есть, но нет Cloudflare cookies

**Решение:**
- Проверьте какие cookies получены
- Возможно нужны другие cookies (не cf_*)
- Попробуйте подождать дольше

---

## 🧪 Ручная проверка cookies:

**В Popup Console выполните:**

```javascript
// Проверка 1: API доступен?
chrome.cookies.getAll({domain: 'czbooks.net'}, (cookies) => {
  console.log('Всего cookies на czbooks.net:', cookies.length);
  cookies.forEach(c => console.log(`  - ${c.name}: ${c.value.substring(0, 20)}...`));
});

// Проверка 2: Web App доступен?
fetch('http://192.168.0.58:5001/api/novels?active_only=true')
  .then(r => r.json())
  .then(data => console.log('Web App novels:', data))
  .catch(e => console.error('Web App error:', e));

// Проверка 3: Разрешения?
chrome.permissions.getAll((permissions) => {
  console.log('Permissions:', permissions);
});
```

---

## 📋 Отправьте мне логи:

**Скопируйте из Popup Console:**
1. Весь вывод после нажатия кнопки
2. Особенно строки с ❌ или ⚠️

**Скопируйте из Background Console:**
1. Весь вывод после "🍪 [Background] Извлекаем cookies"

---

## 🎯 Самые частые проблемы и решения:

| Симптом | Причина | Решение |
|---------|---------|---------|
| Response status: 0 | Web App недоступен | Запустите Web App |
| Новелла не найдена | Не создана или неактивна | Создайте/активируйте |
| Получено cookies: 0 | Cloudflare не пройден | Подождите дольше (20 сек) |
| cf_clearance: ❌ | Нет Cloudflare cookie | Откройте вручную и проверьте |
| CORS error | Разрешения не выданы | chrome://extensions/ → Details → Site access |

---

## 🚀 После исправления:

1. Обновите расширение (Load unpacked)
2. Перезапустите попытку
3. Проверьте логи снова
4. Отправьте результат

---

**Архив с логированием: 21 KB**
**http://192.168.0.58:5001/download-extension**
