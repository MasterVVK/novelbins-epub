# 🔍 Отладка: Не находит cookies

## Что проверить в F12

### 1. Откройте консоль расширения:

**Способ A: Через popup**
```
1. Откройте popup расширения (кликните на иконку)
2. Правый клик в любом месте popup
3. "Inspect" (Проверить)
4. Откроется DevTools для popup
5. Вкладка "Console"
```

**Способ B: Через chrome://extensions/**
```
1. chrome://extensions/
2. Найдите "Novelbins Cookie Extractor"
3. Нажмите "Inspect views: service worker" (если есть)
4. Или "Errors" (если есть ошибки)
```

---

## 2. Что искать в Console:

### Ожидаемые логи при успехе:

```javascript
// При нажатии кнопки "Автоматически получить Cookies"
Открываем конкретную новеллу: https://czbooks.net/n/ul6pe

// После 15 секунд
Найдена новелла czbooks.net, ID: 11

// Если успешно
{success: true, cookies: {count: 12, cloudflareCount: 3, ...}}
```

### Возможные ошибки:

```javascript
// Ошибка 1: Не удалось получить URL новеллы
Не удалось получить URL новеллы, используем главную страницу

// Ошибка 2: CORS
Access to fetch at 'http://192.168.0.58:5001/api/novels' from origin 'chrome-extension://...'
has been blocked by CORS policy

// Ошибка 3: Не удалось найти новеллу
Не удалось найти новеллу, сохраняем cookies глобально: ...

// Ошибка 4: 0 cookies
{success: true, cookies: {count: 0, cloudflareCount: 0, ...}}
```

---

## 3. Проверьте Network вкладку:

**В DevTools popup:**
1. Вкладка "Network"
2. Нажмите "🚀 Автоматически получить Cookies"
3. Смотрите запросы:

### Ожидаемые запросы:

```
GET http://192.168.0.58:5001/api/novels?active_only=true
  Status: 200
  Response: {success: true, novels: [{id: 11, ...}]}

(ждем 15 сек)

POST http://192.168.0.58:5001/api/cloudflare-auth/save-cookies
  Status: 200
  Request: {cookies: "...", novel_id: 11}
  Response: {success: true, message: "..."}
```

---

## 4. Проверьте вкладку с czbooks.net:

**После нажатия кнопки:**
1. Должна открыться фоновая вкладка: https://czbooks.net/n/ul6pe
2. Найдите её в списке вкладок (может быть не активна)
3. Откройте эту вкладку
4. F12 → Console

### Что проверить:

```javascript
// Проверьте cookies вручную
document.cookie
// Должно показать что-то вроде:
// "cf_clearance=xxx; __cf_bm=yyy; _cfuvid=zzz; ..."

// Если пусто или только 1-2 cookie - Cloudflare challenge не пройден
```

---

## 5. Проверьте Cloudflare challenge:

**Вручную откройте:**
```
https://czbooks.net/n/ul6pe
```

### Что должно произойти:

1. **~3-5 секунд:** "Checking your browser..."
2. **~5-7 секунд:** Страница загрузилась
3. **~10-15 секунд:** Полная загрузка контента

### Если видите:

- ❌ "Cloudflare checking" зависает навсегда → Проблема с IP/VPN
- ❌ "Access Denied" → Заблокирован IP
- ❌ "Captcha" → Нужно решить капчу вручную
- ✅ Страница загрузилась → Все OK

---

## 6. Проверьте разрешения расширения:

```
chrome://extensions/
→ "Novelbins Cookie Extractor"
→ "Details"
→ Прокрутите вниз до "Site access"
```

### Должно быть:

```
Site access: On specific sites
  https://czbooks.net/*  ✅ Allowed
  http://192.168.0.58:5001/*  ✅ Allowed
```

Если не разрешено - нажмите "Add" и добавьте домены.

---

## 7. Проверьте chrome.cookies API:

**В Console расширения (popup DevTools):**

```javascript
// Проверьте что API доступен
chrome.cookies
// Должно показать: {get: ƒ, getAll: ƒ, set: ƒ, remove: ƒ, ...}

// Попробуйте получить cookies вручную
chrome.cookies.getAll({domain: 'czbooks.net'}, (cookies) => {
  console.log('Всего cookies:', cookies.length);
  console.log('Cookies:', cookies);
  console.log('cf_clearance:', cookies.find(c => c.name === 'cf_clearance'));
});

// Должно показать массив cookies
```

---

## 8. Проверьте время ожидания:

Возможно 15 секунд недостаточно для вашего интернета.

**Временное решение:**

Откройте `popup.js` и найдите строку:
```javascript
await new Promise(resolve => setTimeout(resolve, 15000));
```

Увеличьте до 20 секунд:
```javascript
await new Promise(resolve => setTimeout(resolve, 20000));
```

Пересоберите архив:
```bash
tar -czf browser_extension.tar.gz browser_extension/
cp browser_extension.tar.gz web_app/app/static/browser_extension.tar.gz
```

---

## 9. Проверьте background service worker:

```
chrome://extensions/
→ "Novelbins Cookie Extractor"
→ "Inspect views: service worker"
```

### В Console background worker:

```javascript
// Должны быть логи при отправке cookies
Найдена новелла czbooks.net, ID: 11
// или
Не удалось найти новеллу, сохраняем cookies глобально: ...
```

---

## 10. Проверьте что новелла существует:

**В терминале сервера:**

```bash
curl http://192.168.0.58:5001/api/novels?active_only=true
```

### Должно вернуть:

```json
{
  "success": true,
  "novels": [
    {
      "id": 11,
      "title": "Forty Millenniums of Cultivation",
      "source_type": "czbooks",
      "source_url": "https://czbooks.net/n/ul6pe",
      ...
    }
  ]
}
```

Если новеллы нет - нужно её создать.

---

## 🔧 Быстрая проверка (пошагово):

### Шаг 1: Откройте popup расширения
→ Правый клик → Inspect

### Шаг 2: В Console выполните:

```javascript
// 1. Проверка API
console.log('Chrome Cookies API:', chrome.cookies ? '✅' : '❌');
console.log('Chrome Tabs API:', chrome.tabs ? '✅' : '❌');

// 2. Проверка Web App
fetch('http://192.168.0.58:5001/api/novels?active_only=true')
  .then(r => r.json())
  .then(data => {
    console.log('Web App response:', data);
    const novel = data.novels.find(n => n.source_type === 'czbooks' || n.source_type === 'czbooks.net');
    console.log('Найдена новелла:', novel ? `ID ${novel.id}` : '❌ НЕТ');
  })
  .catch(e => console.error('Ошибка Web App:', e));

// 3. Проверка cookies на czbooks.net
chrome.cookies.getAll({domain: 'czbooks.net'}, (cookies) => {
  console.log('Cookies на czbooks.net:', cookies.length);
  console.log('cf_clearance:', cookies.find(c => c.name === 'cf_clearance') ? '✅' : '❌');
  console.log('__cf_bm:', cookies.find(c => c.name === '__cf_bm') ? '✅' : '❌');
});
```

### Шаг 3: Скопируйте результат и отправьте мне

---

## 📋 Чеклист проблем:

- [ ] Chrome Cookies API доступен?
- [ ] Chrome Tabs API доступен?
- [ ] Web App отвечает на /api/novels?
- [ ] Новелла ID 11 существует?
- [ ] source_type = 'czbooks' или 'czbooks.net'?
- [ ] Разрешения на https://czbooks.net/* выданы?
- [ ] Cloudflare challenge проходит?
- [ ] Cookies на czbooks.net существуют?
- [ ] cf_clearance cookie присутствует?
- [ ] Время ожидания достаточное (15 сек)?

---

## 🚨 Самые частые проблемы:

### Проблема 1: Cloudflare не проходит за 15 секунд
**Решение:** Увеличьте время до 20-30 секунд

### Проблема 2: IP заблокирован Cloudflare
**Решение:** Используйте VPN или другой IP

### Проблема 3: Разрешения не выданы
**Решение:** chrome://extensions/ → Details → Site access → Add sites

### Проблема 4: Web App недоступен
**Решение:** Проверьте что Web App запущен: http://192.168.0.58:5001

---

**Запустите быструю проверку (Шаг 1-3) и отправьте результат!**
