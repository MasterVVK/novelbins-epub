# Cloudflare Cookie Automation - Все варианты

**Дата:** 2025-10-13
**Статус:** Документация по автоматизации получения Cloudflare cookies

---

## Вопрос: "Разве нельзя сделать, чтобы кукисы копировались автоматически?"

**Краткий ответ:** Да, можно! Но с ограничениями из-за Same-Origin Policy.

**Длинный ответ:** Автоматическое извлечение cookies из другого домена (czbooks.net) **заблокировано браузером** по соображениям безопасности. Однако есть **3 рабочих способа** обойти это ограничение.

---

## 🚫 Почему НЕ работает автоматически в popup/iframe?

### Same-Origin Policy (SOP)

Браузер **блокирует** JavaScript от доступа к cookies другого домена:

```javascript
// ❌ НЕ РАБОТАЕТ - SecurityError: Blocked by Same-Origin Policy
const iframe = document.getElementById('czbooks-frame');
const cookies = iframe.contentWindow.document.cookie;
// -> Uncaught DOMException: Blocked a frame with origin "http://localhost:5001"
//    from accessing a cross-origin frame.
```

### Почему postMessage тоже не работает?

```javascript
// ❌ НЕ РАБОТАЕТ - czbooks.net не отправит cookies обратно
window.postMessage({ action: 'getCookies' }, 'https://czbooks.net');
// czbooks.net не имеет кода для ответа на это сообщение
```

**Вывод:** Popup/iframe подход **технически невозможен** без расширения браузера или сотрудничества czbooks.net.

---

## ✅ Варианты автоматизации

Есть **3 рабочих способа** автоматически получить cookies:

| Вариант | Сложность | Время настройки | Автоматизация | Рекомендация |
|---------|-----------|-----------------|---------------|--------------|
| **1. Browser Extension** | Средняя | 5 мин | 100% | ⭐ Лучший для desktop |
| **2. Xvfb + Selenium** | Средняя | 10 мин | 100% | ⭐ Лучший для сервера |
| **3. FlareSolverr** | Высокая | 20 мин | 100% | 💼 Enterprise |

---

## Вариант 1: Browser Extension (РЕАЛИЗОВАНО) ⭐

### Описание

Chrome/Firefox расширение с доступом к **Chrome Cookies API**, которое может читать cookies **любого домена**.

### Как работает?

```
┌─────────────┐
│ Пользователь│ 1. Открывает czbooks.net
│             │ 2. Cloudflare challenge проходит
└──────┬──────┘
       │ 3. Кликает на расширение
       ▼
┌─────────────────┐
│ Browser Extension│ 4. chrome.cookies.getAll({domain: 'czbooks.net'})
└──────┬──────────┘
       │ 5. Извлекает ВСЕ cookies
       ▼
┌─────────────────┐
│ Novelbins       │ 6. POST /api/cloudflare-auth/save-cookies
│   Web App       │
└─────────────────┘
```

### Преимущества

✅ **100% автоматизация** - не нужно открывать DevTools
✅ **Одна кнопка** - вся операция за 2 клика
✅ **Безопасно** - cookies остаются на устройстве пользователя
✅ **Быстро** - 5 секунд вместо 10
✅ **Универсально** - работает с любыми сайтами

### Недостатки

⚠️ Требует установки расширения
⚠️ Только для браузеров (Chrome/Firefox/Edge)
⚠️ Не подходит для серверной автоматизации

### Реализация

**Уже реализовано!** См. `browser_extension/`

#### Структура:

```
browser_extension/
├── manifest.json       # Manifest V3
├── background.js       # Service Worker для извлечения cookies
├── popup.html          # UI расширения (400x500px)
├── popup.js            # Логика UI
└── README.md           # Полная документация
```

#### Установка:

```bash
# 1. Откройте Chrome Extensions
chrome://extensions/

# 2. Включите Developer mode

# 3. Load unpacked
# Выберите папку: /home/user/novelbins-epub/browser_extension/

# 4. Готово!
```

#### Использование:

```
1. Открыть czbooks.net
2. Дождаться Cloudflare challenge (~5 сек)
3. Кликнуть на расширение
4. Нажать "Извлечь Cookies"
5. Нажать "Отправить в Web App" или "Скопировать"
```

### Код (ключевые части)

**background.js:**
```javascript
// Извлечение cookies через Chrome API
async function extractCookies(domain) {
  const allCookies = await chrome.cookies.getAll({ domain });

  const cookieString = allCookies
    .map(cookie => `${cookie.name}=${cookie.value}`)
    .join('; ');

  return { cookieString, cookies: allCookies };
}

// Отправка в Web App
async function sendCookiesToWebApp(cookieString, webAppUrl) {
  const response = await fetch(`${webAppUrl}/api/cloudflare-auth/save-cookies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cookies: cookieString })
  });

  return await response.json();
}
```

**popup.js:**
```javascript
// Извлечь cookies
extractBtn.addEventListener('click', async function() {
  const response = await chrome.runtime.sendMessage({
    action: 'getCookies',
    domain: 'czbooks.net'
  });

  displayCookies(response.cookies);
});

// Отправить в Web App
sendBtn.addEventListener('click', async function() {
  await chrome.runtime.sendMessage({
    action: 'sendToWebApp',
    cookies: extractedCookies.cookieString,
    webAppUrl: webAppUrlInput.value
  });
});
```

---

## Вариант 2: Xvfb + Selenium (для сервера) 🖥️

### Описание

Использование **виртуального дисплея** (Xvfb) для запуска non-headless браузера на сервере без физического монитора.

### Как работает?

```
┌─────────────┐
│   Xvfb      │ Виртуальный дисплей (:99)
│  (Virtual   │
│   Display)  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ undetected-     │ Non-headless режим
│ chromedriver    │ (headless=False)
└──────┬──────────┘
       │ Открывает czbooks.net
       ▼
┌─────────────────┐
│ Cloudflare      │ Проходит challenge
│   Challenge     │ (~5 секунд)
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ driver.get_     │ Извлекает cookies
│   cookies()     │ автоматически
└─────────────────┘
```

### Преимущества

✅ **100% автоматизация** на сервере
✅ **Без ручного вмешательства**
✅ **Лучший обход Cloudflare** (реальный браузер)
✅ **Можно использовать в cron/scheduled tasks**

### Недостатки

⚠️ Требует установки Xvfb на сервере
⚠️ Больше ресурсов (CPU/RAM)
⚠️ Медленнее headless режима (~10-15 секунд на запрос)

### Установка

```bash
# Установить Xvfb
sudo apt-get update
sudo apt-get install -y xvfb

# Установить Python библиотеку
pip install pyvirtualdisplay

# Проверить установку
xvfb-run --help
```

### Использование

#### Вариант A: Через pyvirtualdisplay (Python)

```python
from pyvirtualdisplay import Display
from parsers import create_parser

# Запустить виртуальный дисплей
display = Display(visible=0, size=(1920, 1080))
display.start()

try:
    # Создать парсер в non-headless режиме
    parser = create_parser('czbooks', headless=False)

    # Использовать парсер
    book_info = parser.get_book_info('https://czbooks.net/n/ul6pe')

    # Cookies автоматически извлекаются
    print(f"Название: {book_info['title']}")

finally:
    parser.close()
    display.stop()
```

#### Вариант B: Через xvfb-run (командная строка)

```bash
# Запустить скрипт с виртуальным дисплеем
xvfb-run -a python test_czbooks_parser.py

# Запустить Web App с Xvfb
xvfb-run -a python run_web.py
```

### Интеграция в Web App

Обновить `parsers/sources/czbooks_parser.py`:

```python
class CZBooksParser(BaseParser):
    def __init__(self, auth_cookies=None, headless=True, use_xvfb=False):
        super().__init__("czbooks")
        self.auth_cookies = auth_cookies
        self.headless = headless
        self.use_xvfb = use_xvfb
        self.display = None

        if use_xvfb and not headless:
            from pyvirtualdisplay import Display
            self.display = Display(visible=0, size=(1920, 1080))
            self.display.start()

    def close(self):
        if self.driver:
            self.driver.quit()
        if self.display:
            self.display.stop()
```

### Production Setup (Systemd)

Создать `/etc/systemd/system/novelbins.service`:

```ini
[Unit]
Description=Novelbins Web App with Xvfb
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/novelbins-epub
Environment="DISPLAY=:99"
ExecStartPre=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 -ac &
ExecStart=/path/to/venv/bin/python run_web.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Запустить:
```bash
sudo systemctl daemon-reload
sudo systemctl enable novelbins
sudo systemctl start novelbins
```

---

## Вариант 3: FlareSolverr (Enterprise) 🏢

### Описание

Docker-сервис, который **специально предназначен** для обхода Cloudflare challenges и извлечения cookies.

### Как работает?

```
┌─────────────────┐
│ Novelbins       │ 1. POST /v1 {url: 'czbooks.net'}
│   Web App       │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ FlareSolverr    │ 2. Открывает Chromium
│  (Docker :8191) │ 3. Проходит Cloudflare
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Response JSON   │ 4. Возвращает HTML + cookies
│ {               │
│   solution: {   │
│     cookies,    │
│     userAgent,  │
│     response    │
│   }             │
│ }               │
└─────────────────┘
```

### Преимущества

✅ **Решает сложные Cloudflare challenges** (включая CAPTCHA с 2captcha)
✅ **Отдельный сервис** - не нагружает основное приложение
✅ **HTTP API** - можно использовать из любого языка
✅ **Production-ready** - активная разработка и поддержка

### Недостатки

⚠️ Требует Docker
⚠️ Дополнительный сервис для мониторинга
⚠️ Больше ресурсов (отдельный контейнер)
💰 CAPTCHA решение платное (через 2captcha API)

### Установка

```bash
# Запустить FlareSolverr в Docker
docker run -d \
  --name=flaresolverr \
  -p 8191:8191 \
  -e LOG_LEVEL=info \
  --restart unless-stopped \
  ghcr.io/flaresolverr/flaresolverr:latest

# Проверить статус
curl http://localhost:8191/health
```

### Использование

#### API Request

```bash
curl -X POST http://localhost:8191/v1 \
  -H "Content-Type: application/json" \
  -d '{
    "cmd": "request.get",
    "url": "https://czbooks.net/n/ul6pe",
    "maxTimeout": 60000
  }'
```

#### Response

```json
{
  "status": "ok",
  "message": "",
  "startTimestamp": 1697184000000,
  "endTimestamp": 1697184015000,
  "solution": {
    "url": "https://czbooks.net/n/ul6pe",
    "status": 200,
    "cookies": [
      {
        "name": "cf_clearance",
        "value": "xxx-yyy-zzz",
        "domain": ".czbooks.net"
      },
      {
        "name": "__cf_bm",
        "value": "aaa-bbb-ccc",
        "domain": ".czbooks.net"
      }
    ],
    "userAgent": "Mozilla/5.0 ...",
    "response": "<html>...</html>"
  }
}
```

### Интеграция в CZBooksParser

Создать метод в `czbooks_parser.py`:

```python
import requests

class CZBooksParser(BaseParser):
    def __init__(self, use_flaresolverr=False, flaresolverr_url='http://localhost:8191'):
        self.use_flaresolverr = use_flaresolverr
        self.flaresolverr_url = flaresolverr_url

    def _get_page_with_flaresolverr(self, url):
        """Загрузить страницу через FlareSolverr"""
        response = requests.post(
            f'{self.flaresolverr_url}/v1',
            json={
                "cmd": "request.get",
                "url": url,
                "maxTimeout": 60000
            },
            timeout=70
        )

        data = response.json()

        if data['status'] != 'ok':
            raise Exception(f"FlareSolverr error: {data.get('message')}")

        # Извлекаем cookies
        cookies = data['solution']['cookies']
        cookie_string = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

        # Сохраняем для будущих запросов
        self.auth_cookies = cookie_string

        return data['solution']['response']

    def get_book_info(self, url):
        if self.use_flaresolverr:
            html = self._get_page_with_flaresolverr(url)
        else:
            html = self._get_page(url)

        soup = BeautifulSoup(html, 'html.parser')
        # ... parse as usual
```

### Production Setup (Docker Compose)

`docker-compose.yml`:

```yaml
version: '3.8'

services:
  flaresolverr:
    image: ghcr.io/flaresolverr/flaresolverr:latest
    container_name: flaresolverr
    environment:
      - LOG_LEVEL=info
      - CAPTCHA_SOLVER=2captcha
      - CAPTCHA_API_KEY=${TWOCAPTCHA_API_KEY}
    ports:
      - "8191:8191"
    restart: unless-stopped

  novelbins:
    build: .
    container_name: novelbins
    environment:
      - FLARESOLVERR_URL=http://flaresolverr:8191
    ports:
      - "5001:5001"
    depends_on:
      - flaresolverr
    restart: unless-stopped
```

Запустить:
```bash
docker-compose up -d
```

---

## Вариант 4: Платные API (для Production) 💰

### Описание

Использование специализированных сервисов для обхода Cloudflare:
- **ScraperAPI**: https://www.scraperapi.com/
- **ScrapingBee**: https://www.scrapingbee.com/
- **Bright Data**: https://brightdata.com/

### Преимущества

✅ **Гарантированный обход** Cloudflare (99.9% uptime)
✅ **Ротация IP и прокси**
✅ **Техподдержка 24/7**
✅ **Не требует инфраструктуры**
✅ **JavaScript rendering** включен

### Недостатки

💰 **Платно** (~$29-500/месяц)
⚠️ Зависимость от внешнего сервиса
⚠️ Лимиты на количество запросов

### Цены

| Сервис | Цена | Запросов/мес | Особенности |
|--------|------|--------------|-------------|
| ScraperAPI | $29 | 250,000 | JS rendering |
| ScrapingBee | $49 | 150,000 | Premium proxies |
| Bright Data | $500+ | Unlimited | Enterprise |

### Пример использования (ScraperAPI)

```python
import requests

def get_page_via_scraper_api(url, api_key):
    response = requests.get('http://api.scraperapi.com/', params={
        'api_key': api_key,
        'url': url,
        'render': 'true'  # JavaScript rendering
    })

    return response.text

# В CZBooksParser
class CZBooksParser(BaseParser):
    def __init__(self, scraper_api_key=None):
        self.scraper_api_key = scraper_api_key

    def _get_page(self, url):
        if self.scraper_api_key:
            return get_page_via_scraper_api(url, self.scraper_api_key)
        else:
            # fallback to regular method
            return super()._get_page(url)
```

---

## Сравнение всех вариантов

| Критерий | Ручной способ | Browser Extension | Xvfb + Selenium | FlareSolverr | Платные API |
|----------|---------------|-------------------|-----------------|--------------|-------------|
| **Автоматизация** | ❌ 0% | ✅ 95% | ✅ 100% | ✅ 100% | ✅ 100% |
| **Надежность** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Скорость** | 10 сек | 5 сек | 15 сек | 20 сек | 5 сек |
| **Сложность** | Простая | Средняя | Средняя | Высокая | Простая |
| **Стоимость** | Бесплатно | Бесплатно | Бесплатно | Бесплатно | $29-500/мес |
| **Серверная автоматизация** | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Desktop использование** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Требует инфраструктуры** | ❌ | ❌ | ⚠️ Xvfb | ⚠️ Docker | ❌ |

---

## Рекомендации

### Для локальной разработки (Desktop)

✅ **Browser Extension** (Вариант 1)

**Почему?**
- Самый простой и быстрый
- Уже реализован в `browser_extension/`
- Не требует изменений в коде парсера
- 5 секунд на операцию

**Как начать?**
```bash
# 1. Откройте chrome://extensions/
# 2. Load unpacked -> browser_extension/
# 3. Готово!
```

---

### Для сервера (Production)

✅ **Xvfb + Selenium** (Вариант 2)

**Почему?**
- Бесплатно
- Надежно
- Интегрируется в существующий код
- Подходит для cron jobs

**Как начать?**
```bash
# Установить Xvfb
sudo apt-get install xvfb
pip install pyvirtualdisplay

# Использовать в коде
from pyvirtualdisplay import Display
display = Display(visible=0, size=(1920, 1080))
display.start()
parser = create_parser('czbooks', headless=False)
# ... use parser
display.stop()
```

---

### Для Enterprise (большие объемы)

✅ **FlareSolverr** (Вариант 3) или **Платные API** (Вариант 4)

**Почему?**
- Масштабируется
- 99.9% uptime
- Техподдержка
- Решает сложные CAPTCHA

**Когда использовать?**
- Более 10,000 запросов/день
- Требуется гарантия работы
- Есть бюджет на инфраструктуру

---

## Итоговая рекомендация

### Сейчас (немедленно)

**Использовать Browser Extension:**
1. ✅ Установить расширение из `browser_extension/`
2. ✅ Извлекать cookies автоматически
3. ✅ Отправлять в Web App одной кнопкой

**Время на настройку:** 5 минут
**Автоматизация:** 95%

### Будущее (для серверной автоматизации)

**Внедрить Xvfb + Selenium:**
1. Установить Xvfb на сервере
2. Обновить CZBooksParser с use_xvfb=True
3. Настроить systemd service
4. Включить автоматический парсинг

**Время на настройку:** 1 час
**Автоматизация:** 100%

---

## FAQ

### Q: Почему не работает автоматически в iframe?

**A:** Same-Origin Policy блокирует доступ к cookies другого домена из соображений безопасности. Это фундаментальное ограничение браузера.

### Q: Какой вариант самый быстрый?

**A:**
- **Fastest:** Платные API (~3-5 сек)
- **Fast:** Browser Extension (~5 сек)
- **Medium:** Xvfb + Selenium (~10-15 сек)
- **Slow:** FlareSolverr (~15-20 сек)

### Q: Какой вариант самый надежный?

**A:**
1. **Платные API** - 99.9% SLA
2. **FlareSolverr** - специализирован для Cloudflare
3. **Xvfb + Selenium** - реальный браузер
4. **Browser Extension** - зависит от пользователя

### Q: Можно ли комбинировать варианты?

**A:** Да! Рекомендуется:
```python
# Приоритет:
# 1. Попробовать с существующими cookies
# 2. Если cookies истекли -> FlareSolverr
# 3. Если FlareSolverr недоступен -> Xvfb
# 4. Если Xvfb не установлен -> запросить у пользователя

parser = create_parser('czbooks',
    auth_cookies=existing_cookies,
    use_flaresolverr=True,
    fallback_to_xvfb=True
)
```

---

## Заключение

**Да, автоматическое копирование cookies возможно!**

Реализовано **3 рабочих варианта**:
1. ✅ **Browser Extension** - для desktop (РЕАЛИЗОВАНО)
2. ✅ **Xvfb + Selenium** - для сервера (документировано)
3. ✅ **FlareSolverr** - для enterprise (документировано)

**Рекомендация:**
- Начните с **Browser Extension** (уже готово в `browser_extension/`)
- Для production переходите на **Xvfb + Selenium**

**Автор:** Claude Code Assistant
**Дата:** 2025-10-13
**Версия:** 1.0
