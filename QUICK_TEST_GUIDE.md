# Быстрое руководство по тестированию

## ✅ Новелла создана! ID: 11

---

## 🚀 Тестирование за 3 шага (10 минут)

### 1️⃣ Установите Browser Extension (3 минуты)

```
chrome://extensions/
→ Developer mode: ON
→ Load unpacked
→ Выберите: /home/user/novelbins-epub/browser_extension/
```

---

### 2️⃣ Извлеките Cloudflare cookies (5 секунд)

```
1. Откройте: https://czbooks.net
2. Подождите ~5 сек (Cloudflare challenge)
3. Кликните на расширение
4. Нажмите: [Извлечь Cookies]
5. Нажмите: [Отправить в Web App]
```

**Ожидаемый результат:**
```
✅ Успешно! Найдено 12 cookies
✅ Cookies успешно отправлены в Web App!
```

---

### 3️⃣ Проверьте новеллу (1 минута)

```
http://192.168.0.58:5001/novel/11
→ Cookies должны быть установлены
→ Можно запускать парсинг
```

---

## 📋 Checklist

- [ ] Browser Extension установлен
- [ ] Cookies извлечены (12 cookies, 3 Cloudflare)
- [ ] Cookies отправлены в Web App
- [ ] Новелла ID 11 обновлена с cookies
- [ ] Парсинг работает

---

## 🔗 Ссылки

```
Dashboard:        http://192.168.0.58:5001
Новелла:          http://192.168.0.58:5001/novel/11
Редактирование:   http://192.168.0.58:5001/edit-novel/11
Расширение:       chrome://extensions/
CZBooks:          https://czbooks.net
```

---

## 📚 Документация

**Быстрый старт:**
- `browser_extension/QUICK_START.md`
- `TEST_BROWSER_EXTENSION.md`

**Подробная:**
- `browser_extension/INSTALLATION.md`
- `BROWSER_EXTENSION_READY.md`
- `CLOUDFLARE_SOLUTION_FINAL.md`

---

## ❓ Проблемы?

### "0 cookies найдено"
→ Подождите 5 сек после загрузки czbooks.net

### "Failed to fetch"
→ Проверьте что Web App запущен: `http://192.168.0.58:5001`

### Cookies не сохраняются
→ Проверьте Console (F12) на ошибки

---

## ✨ Готово!

**Новелла:** ✅ Создана (ID: 11)
**Расширение:** ✅ Готово к установке
**Документация:** ✅ Готова

**Начните:** `browser_extension/QUICK_START.md`

---

**Forty Millenniums of Cultivation** (修真四万年)
**URL:** https://czbooks.net/n/ul6pe
**Статус:** Готово к парсингу с cookies
