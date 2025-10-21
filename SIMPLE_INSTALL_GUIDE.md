# Browser Extension - Простая установка

## ✅ Архив доступен по адресу Web App!

---

## 🚀 Быстрая установка (3 шага)

### Шаг 1: Скачайте архив (на ПК с браузером)

Откройте в браузере:
```
http://192.168.0.58:5001/static/browser_extension.tar.gz
```

Браузер автоматически скачает файл (17 KB)

---

### Шаг 2: Распакуйте

**Windows:**
- Правый клик на файл
- 7-Zip → Extract Here
- (Если нет 7-Zip, установите: https://www.7-zip.org/)

**Linux/Mac:**
```bash
tar -xzf browser_extension.tar.gz
```

Появится папка: `browser_extension/`

---

### Шаг 3: Установите в Chrome

1. Откройте: `chrome://extensions/`
2. Включите: **Developer mode** ⚙️ (справа сверху)
3. Нажмите: **Load unpacked** 📂
4. Выберите папку: `browser_extension/`
5. Готово! ✅

---

## 🎯 Использование (5 секунд)

### 1. Откройте czbooks.net
```
https://czbooks.net
```
Подождите ~5 сек (Cloudflare)

### 2. Откройте расширение
Кликните на иконку в панели Chrome

### 3. Извлеките cookies
**[🔍 Извлечь Cookies]** → ✅ Найдено 12 cookies

### 4. Отправьте в Web App
**[📤 Отправить в Web App]** → ✅ Отправлено!

---

## 🔍 Проверка

### На сервере (192.168.0.58):

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
        print('✅ SUCCESS! Cookies получены!')
        print(f'Length: {len(novel.auth_cookies)} символов')
    else:
        print('❌ Cookies ещё не получены')
" 2>&1 | grep -E "(SUCCESS|Cookies|Length|❌)"
```

---

## 📋 Checklist

- [ ] Скачан: `http://192.168.0.58:5001/static/browser_extension.tar.gz`
- [ ] Распакован в папку `browser_extension/`
- [ ] Установлен в Chrome
- [ ] Cookies извлечены с czbooks.net
- [ ] Cookies отправлены в Web App
- [ ] Проверка на сервере: ✅ SUCCESS

---

## ❗ Проблемы?

### "Download failed"
→ Проверьте что Web App работает: `http://192.168.0.58:5001`

### "Can't extract archive" (Windows)
→ Установите 7-Zip: https://www.7-zip.org/

### "Failed to fetch" при отправке
→ Проверьте URL в расширении: `http://192.168.0.58:5001`

---

## 📚 Документация

После установки расширения:
- `browser_extension/QUICK_START.md` - быстрый старт
- `browser_extension/README.md` - полная документация

---

## ✨ Готово!

**Скачать:** http://192.168.0.58:5001/static/browser_extension.tar.gz
**Новелла:** http://192.168.0.58:5001/novel/11
**Размер:** 17 KB
**Время:** 5 минут

---

**Создано:** 2025-10-13
**Web App:** http://192.168.0.58:5001
**Новелла ID:** 11
