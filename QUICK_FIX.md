# ⚡ БЫСТРОЕ РЕШЕНИЕ: Не находит cookies

## 🎯 Проблема: `ERR_BLOCKED_BY_CLIENT`

**AdBlock блокирует скрипты на czbooks.net!**

---

## ✅ Решение за 30 секунд:

### Используйте Incognito Mode (без AdBlock):

```
1. chrome://extensions/
   → "Novelbins Cookie Extractor"
   → Details
   → ✅ "Allow in Incognito"

2. Ctrl+Shift+N (открыть Incognito окно)

3. В Incognito:
   - Кликните на иконку расширения
   - Нажмите "🚀 Автоматически получить Cookies"
   - Ждите 15 секунд
   - ✅ Готово!
```

**В Incognito нет AdBlock → всё работает!**

---

## ✅ Альтернатива: Отключить AdBlock

```
1. Откройте https://czbooks.net
2. Найдите иконку AdBlock в панели
3. Кликните → "Don't run on pages on this domain"
4. Готово!
```

Теперь используйте расширение как обычно.

---

## 🔍 Проверка:

Откройте: https://czbooks.net/n/ul6pe

**F12 → Console НЕ должно быть:**
```
❌ Failed to load resource: net::ERR_BLOCKED_BY_CLIENT
```

**F12 → Console выполните:**
```javascript
document.cookie
```

**Должно показать:**
```
"cf_clearance=xxx; __cf_bm=yyy; ..."
```

---

## 📚 Подробная инструкция:

Смотрите файл: **SOLUTION_ADBLOCK.md**

---

**Выберите один из способов и попробуйте снова!** 🚀
