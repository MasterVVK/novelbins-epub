# Установка Browser Extension на удалённом ПК

**Ситуация:** Web App запущен на одном ПК (192.168.0.58), браузер на другом ПК.

**Решение:** Перенести папку `browser_extension/` на ПК с браузером.

---

## 📦 Шаг 1: Скопировать папку расширения на ПК с браузером

### Вариант A: Через сеть (SMB/NFS/SSH)

**Если у вас есть доступ к серверу с ПК:**

#### Через SCP (Linux/Mac):
```bash
# На ПК с браузером выполните:
scp -r user@192.168.0.58:/home/user/novelbins-epub/browser_extension ~/Downloads/
```

#### Через WinSCP (Windows):
1. Откройте WinSCP
2. Подключитесь к `192.168.0.58`
3. Скопируйте папку:
   ```
   /home/user/novelbins-epub/browser_extension/
   ```
4. Сохраните на ПК с браузером (например, в `C:\Downloads\browser_extension\`)

#### Через общую папку (Samba):
1. Если у вас настроена сетевая папка
2. Скопируйте папку `browser_extension/` в общую папку
3. Откройте на ПК с браузером

---

### Вариант B: Создать архив и передать

**На сервере (192.168.0.58):**

```bash
# Создать архив
cd /home/user/novelbins-epub
tar -czf browser_extension.tar.gz browser_extension/

# Или ZIP архив
zip -r browser_extension.zip browser_extension/
```

**Затем передайте файл:**
- Через email
- Через USB флешку
- Через облако (Google Drive, Dropbox)
- Через веб-сервер (см. Вариант C)

---

### Вариант C: Через временный веб-сервер (БЫСТРО)

**На сервере (192.168.0.58):**

```bash
cd /home/user/novelbins-epub

# Создать архив
tar -czf browser_extension.tar.gz browser_extension/

# Запустить простой веб-сервер
python3 -m http.server 8000
```

**На ПК с браузером:**

```
1. Откройте браузер
2. Перейдите на: http://192.168.0.58:8000
3. Скачайте: browser_extension.tar.gz
4. Распакуйте в удобную папку
```

---

### Вариант D: Я создам архив для вас

Давайте создам архив прямо сейчас:

```bash
cd /home/user/novelbins-epub
tar -czf browser_extension.tar.gz browser_extension/
```

Затем вы сможете скачать его через Web App или веб-сервер.

---

## 🚀 Шаг 2: Установить расширение на ПК с браузером

**После того как папка `browser_extension/` скопирована:**

### 1. Откройте Chrome Extensions

```
chrome://extensions/
```

### 2. Включите Developer Mode

Переключатель в правом верхнем углу → **ON**

### 3. Load Unpacked

1. Нажмите **"Load unpacked"**
2. Выберите папку `browser_extension/` (на вашем ПК)
3. Нажмите **"Select Folder"**

### 4. Закрепите расширение

1. Кликните иконку **пазла** в панели Chrome
2. Найдите **"Novelbins Cookie Extractor"**
3. Нажмите **булавку** (pin)

✅ **Расширение установлено!**

---

## 🎯 Шаг 3: Тестирование

### 1. Откройте czbooks.net

```
https://czbooks.net
```

Подождите ~5 секунд (Cloudflare challenge)

### 2. Откройте расширение

Кликните на иконку расширения

### 3. Проверьте настройки

В поле **"Web App URL"** должно быть:
```
http://192.168.0.58:5001
```

✅ Если URL правильный - продолжайте
❌ Если нет - исправьте вручную

### 4. Извлеките cookies

1. Нажмите: **[🔍 Извлечь Cookies]**
2. Должно появиться:
   ```
   ✅ Успешно! Найдено 12 cookies
   ```

### 5. Отправьте в Web App

1. Нажмите: **[📤 Отправить в Web App]**
2. Должно появиться:
   ```
   ✅ Cookies успешно отправлены в Web App!
   ```

---

## 🔍 Проверка работы

### На ПК с браузером (где расширение):

**Проверка 1: Расширение установлено**
```
chrome://extensions/
→ Novelbins Cookie Extractor ✓
```

**Проверка 2: Cookies извлечены**
```
Расширение → Извлечь Cookies
→ ✅ Найдено 12 cookies
```

**Проверка 3: Отправка работает**
```
Расширение → Отправить в Web App
→ ✅ Cookies успешно отправлены!
```

---

### На сервере (192.168.0.58):

**Проверка 4: Web App получил cookies**

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
        print('✅ Cookies получены Web App!')
        print(f'   Length: {len(novel.auth_cookies)} символов')
        print(f'   Contains cf_clearance: {\"cf_clearance\" in novel.auth_cookies}')
    else:
        print('❌ Cookies ещё не получены')
        print('   Отправьте через Browser Extension')
" 2>&1 | grep -v INFO
```

---

## ❗ Устранение неполадок

### Проблема: "Failed to fetch" при отправке

**Причина:** Браузер не может подключиться к `192.168.0.58:5001`

**Решение:**

1. **Проверьте сетевое подключение:**
   ```bash
   # На ПК с браузером
   ping 192.168.0.58
   ```

2. **Проверьте что Web App доступен:**
   ```
   http://192.168.0.58:5001
   ```
   Откройте в браузере - должна открыться страница Web App

3. **Проверьте firewall на сервере:**
   ```bash
   # На сервере
   sudo ufw status
   sudo ufw allow 5001/tcp
   ```

4. **Проверьте что Web App слушает на 0.0.0.0:**
   ```bash
   # На сервере
   netstat -tlnp | grep 5001
   ```
   Должно быть: `0.0.0.0:5001` (не 127.0.0.1:5001)

---

### Проблема: CORS error

**Симптомы:** В Console (F12) видите:
```
Access to fetch at 'http://192.168.0.58:5001/api/...'
has been blocked by CORS policy
```

**Решение:** Добавить CORS поддержку в Web App

**На сервере:**

```bash
# Установить flask-cors
pip install flask-cors
```

Затем добавьте в `web_app/app/__init__.py`:

```python
from flask_cors import CORS

def create_app():
    app = Flask(__name__)

    # Enable CORS for browser extension
    CORS(app, resources={
        r"/api/cloudflare-auth/*": {
            "origins": ["chrome-extension://*"]
        }
    })

    # ... rest of the code
```

Перезапустите Web App:
```bash
# Ctrl+C для остановки
python run_web.py
```

---

### Проблема: Расширение не видит правильный URL

**Решение:** Исправьте URL вручную в расширении

1. Откройте расширение
2. В поле "Web App URL" измените на:
   ```
   http://192.168.0.58:5001
   ```
3. URL автоматически сохранится

---

## 📁 Структура папки для копирования

**Убедитесь что скопировали всю папку:**

```
browser_extension/
├── manifest.json          ✓ Обязательно
├── background.js          ✓ Обязательно
├── popup.html             ✓ Обязательно
├── popup.js               ✓ Обязательно
├── icons/                 ✓ Обязательно
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
├── README.md              (опционально)
├── QUICK_START.md         (опционально)
└── INSTALLATION.md        (опционально)
```

**Минимум необходимых файлов:**
- `manifest.json`
- `background.js`
- `popup.html`
- `popup.js`
- `icons/icon16.png, icon48.png, icon128.png`

---

## 🚀 Быстрый вариант: Создать архив

**Хотите, чтобы я создал архив прямо сейчас?**

Скажите "создай архив" и я выполню:

```bash
cd /home/user/novelbins-epub
tar -czf browser_extension.tar.gz browser_extension/

# Затем запустим веб-сервер для скачивания
python3 -m http.server 8000
```

Вы сможете скачать по адресу:
```
http://192.168.0.58:8000/browser_extension.tar.gz
```

---

## ✅ Checklist

- [ ] Папка `browser_extension/` скопирована на ПК с браузером
- [ ] Расширение установлено в Chrome
- [ ] Web App доступен с ПК с браузером (`http://192.168.0.58:5001`)
- [ ] Cookies успешно извлечены (12 cookies, 3 Cloudflare)
- [ ] Cookies отправлены в Web App
- [ ] Новелла ID 11 получила cookies

---

## 📚 Документация

- `browser_extension/QUICK_START.md` - быстрая установка
- `browser_extension/INSTALLATION.md` - подробная инструкция
- `QUICK_TEST_GUIDE.md` - быстрое тестирование

---

**Готово к установке!**

Выберите удобный способ копирования папки и следуйте инструкциям.

---

**Создано:** 2025-10-13
**Web App:** http://192.168.0.58:5001
**Новелла ID:** 11
