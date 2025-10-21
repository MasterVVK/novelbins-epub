# Скачать Browser Extension

**Архив готов!** Размер: 17KB

---

## 📦 Способ 1: Через временный веб-сервер (РЕКОМЕНДУЕТСЯ)

### На сервере (192.168.0.58):

```bash
cd /home/user/novelbins-epub

# Запустить простой веб-сервер
python3 -m http.server 8000
```

Сервер запустится и покажет:
```
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
```

### На ПК с браузером:

1. **Откройте браузер**

2. **Перейдите на:**
   ```
   http://192.168.0.58:8000
   ```

3. **Скачайте файл:**
   ```
   browser_extension.tar.gz  (17 KB)
   ```
   Кликните на файл для скачивания

4. **Распакуйте:**

   **Linux/Mac:**
   ```bash
   tar -xzf browser_extension.tar.gz
   ```

   **Windows:**
   - Используйте 7-Zip или WinRAR
   - Правый клик → Extract Here

5. **Готово!** Папка `browser_extension/` распакована

### Остановить веб-сервер:

На сервере нажмите `Ctrl+C`

---

## 📦 Способ 2: Через SCP (Linux/Mac)

**На ПК с браузером:**

```bash
# Скачать архив
scp user@192.168.0.58:/home/user/novelbins-epub/browser_extension.tar.gz ~/Downloads/

# Распаковать
cd ~/Downloads
tar -xzf browser_extension.tar.gz

# Готово!
ls browser_extension/
```

---

## 📦 Способ 3: Через WinSCP (Windows)

1. **Откройте WinSCP**

2. **Подключитесь к серверу:**
   ```
   Hostname: 192.168.0.58
   Username: user
   ```

3. **Перейдите в папку:**
   ```
   /home/user/novelbins-epub/
   ```

4. **Скачайте файл:**
   - Найдите: `browser_extension.tar.gz`
   - Перетащите на локальный ПК

5. **Распакуйте:**
   - Используйте 7-Zip или WinRAR

---

## 📦 Способ 4: Через Web App (если есть доступ к файлам)

Если ваш Web App поддерживает скачивание файлов:

```
http://192.168.0.58:5001/static/browser_extension.tar.gz
```

(Требует настройки - см. ниже)

---

## 🚀 После скачивания

### 1. Убедитесь что папка распакована правильно:

```
browser_extension/
├── manifest.json
├── background.js
├── popup.html
├── popup.js
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

### 2. Установите расширение в Chrome:

```
1. chrome://extensions/
2. Developer mode → ON
3. Load unpacked
4. Выберите папку: browser_extension/
```

### 3. Проверьте Web App URL:

Откройте расширение и убедитесь что URL:
```
http://192.168.0.58:5001
```

✅ **Готово к использованию!**

---

## 🔍 Проверка

**Файл существует на сервере:**
```bash
ls -lh /home/user/novelbins-epub/browser_extension.tar.gz
# Должно показать: 17K
```

**Содержимое архива:**
```bash
tar -tzf browser_extension.tar.gz | head -20
```

---

## ❗ Устранение неполадок

### "Connection refused" при http://192.168.0.58:8000

**Решение:**
1. Убедитесь что веб-сервер запущен на сервере:
   ```bash
   python3 -m http.server 8000
   ```

2. Проверьте firewall:
   ```bash
   sudo ufw allow 8000/tcp
   ```

3. Проверьте что сервер слушает на 0.0.0.0:
   ```bash
   netstat -tlnp | grep 8000
   ```

---

### Архив не распаковывается

**Windows:**
- Установите 7-Zip: https://www.7-zip.org/
- Правый клик на файл → 7-Zip → Extract Here

**Mac:**
- Двойной клик на файл
- Или: `tar -xzf browser_extension.tar.gz`

**Linux:**
```bash
tar -xzf browser_extension.tar.gz
```

---

## 📚 Следующие шаги

После установки расширения:

1. **См. быстрый старт:**
   `browser_extension/QUICK_START.md`

2. **Тестирование:**
   `QUICK_TEST_GUIDE.md`

3. **Подробная инструкция:**
   `INSTALL_EXTENSION_REMOTE.md`

---

## ✅ Checklist

- [ ] Архив `browser_extension.tar.gz` скачан (17 KB)
- [ ] Архив распакован
- [ ] Папка `browser_extension/` содержит все файлы
- [ ] Расширение установлено в Chrome
- [ ] Web App URL: `http://192.168.0.58:5001`

---

**Готово!**

Скачайте архив любым удобным способом и установите расширение.

---

**Создано:** 2025-10-13
**Размер архива:** 17 KB
**Файл:** `/home/user/novelbins-epub/browser_extension.tar.gz`
