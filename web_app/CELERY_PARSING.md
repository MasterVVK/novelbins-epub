# Celery парсинг с Xvfb для czbooks.net

## Обзор

Система фонового парсинга через Celery с поддержкой:
- ✅ Работа с czbooks.net через SOCKS5 прокси
- ✅ Non-headless Chrome с Xvfb для обхода Cloudflare
- ✅ Отслеживание прогресса в реальном времени
- ✅ Возможность отмены задачи
- ✅ API endpoints для управления

## Архитектура

```
Web App (Flask)
    ↓ запускает задачу
Celery Worker (с Xvfb)
    ↓ использует
undetected-chromedriver (non-headless)
    ↓ через
SOCKS5 Proxy (192.168.0.61:1080)
    ↓ парсит
czbooks.net (обход Cloudflare)
```

## Установка

### 1. Зависимости

```bash
# Redis (брокер сообщений)
sudo apt-get install redis-server
sudo systemctl start redis-server

# Xvfb (виртуальный дисплей)
sudo apt-get install xvfb

# Python зависимости
pip install celery redis
```

### 2. Конфигурация

В `config.py` или `.env`:

```python
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
```

### 3. База данных

Добавлено поле `parsing_task_id` в модель Novel:

```sql
ALTER TABLE novels ADD COLUMN parsing_task_id VARCHAR(255);
```

## Запуск

### Вариант 1: Скрипт (рекомендуется)

```bash
cd web_app
./start_celery_worker.sh
```

Скрипт автоматически:
- ✅ Проверяет зависимости (xvfb, redis)
- ✅ Запускает Redis если не запущен
- ✅ Активирует venv
- ✅ Запускает Celery worker с Xvfb

### Вариант 2: Вручную

```bash
# В web_app/
source ../.venv/bin/activate
xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
    celery -A app.celery worker \
    --loglevel=INFO \
    --concurrency=1 \
    --pool=solo
```

### Вариант 3: Systemd Service

Создайте `/etc/systemd/system/novel-celery-worker.service`:

```ini
[Unit]
Description=Novel Translator Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/novelbins-epub/web_app
Environment="PATH=/home/user/novelbins-epub/.venv/bin"
Environment="FLASK_APP=app:create_app"
Environment="DISPLAY=:99"
ExecStart=/home/user/novelbins-epub/web_app/start_celery_worker.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable novel-celery-worker
sudo systemctl start novel-celery-worker
sudo systemctl status novel-celery-worker
```

## API Endpoints

### 1. Запуск парсинга

```bash
POST /api/novels/{novel_id}/parse

Body:
{
  "start_chapter": 1,      # опционально
  "max_chapters": 10       # опционально
}

Response:
{
  "success": true,
  "message": "Парсинг запущен",
  "task_id": "abc123...",
  "novel_id": 11
}
```

### 2. Получение статуса

```bash
GET /api/novels/{novel_id}/parse/status

Response (в процессе):
{
  "success": true,
  "parsing": true,
  "task_id": "abc123...",
  "state": "PROGRESS",
  "progress": 45,
  "current_status": "Парсинг главы 45/100",
  "current_chapter": 45,
  "saved_chapters": 44,
  "parsed_chapters": 44,
  "total_chapters": 100
}

Response (завершено):
{
  "success": true,
  "parsing": false,
  "completed": true,
  "message": "Парсинг завершен. Сохранено 100 глав из 100",
  "saved_chapters": 100,
  "total_processed": 100
}
```

### 3. Отмена парсинга

```bash
POST /api/novels/{novel_id}/parse/cancel

Response:
{
  "success": true,
  "message": "Парсинг отменен",
  "task_id": "abc123..."
}
```

### 4. Статус любой задачи

```bash
GET /api/tasks/{task_id}/status

Response:
{
  "success": true,
  "task_id": "abc123...",
  "state": "PROGRESS",
  "ready": false,
  "info": {
    "status": "Парсинг главы 10/100",
    "progress": 10
  }
}
```

## Использование в JavaScript

```javascript
// Запуск парсинга
async function startParsing(novelId) {
  const response = await fetch(`/api/novels/${novelId}/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      start_chapter: 1,
      max_chapters: 100
    })
  });

  const data = await response.json();
  if (data.success) {
    console.log('Парсинг запущен:', data.task_id);
    // Начать опрос статуса
    pollParsingStatus(novelId);
  }
}

// Опрос статуса
function pollParsingStatus(novelId) {
  const intervalId = setInterval(async () => {
    const response = await fetch(`/api/novels/${novelId}/parse/status`);
    const data = await response.json();

    if (!data.parsing) {
      clearInterval(intervalId);
      console.log('Парсинг завершен');
      return;
    }

    // Обновить UI
    updateProgressBar(data.progress);
    updateStatus(data.current_status);

  }, 2000); // Каждые 2 секунды
}

// Отмена парсинга
async function cancelParsing(novelId) {
  const response = await fetch(`/api/novels/${novelId}/parse/cancel`, {
    method: 'POST'
  });

  const data = await response.json();
  if (data.success) {
    console.log('Парсинг отменен');
  }
}
```

## Celery Task

Основная задача находится в `app/celery_tasks.py`:

```python
@celery.task(bind=True, base=CallbackTask, soft_time_limit=86400)
def parse_novel_chapters_task(self, novel_id, start_chapter=None,
                               max_chapters=None, use_xvfb=True):
    # Создание парсера
    parser = create_parser_from_url(...)

    # Парсинг с отслеживанием прогресса
    for i, ch in enumerate(chapters):
        # Проверка отмены
        if task_cancelled():
            return {'status': 'cancelled'}

        # Обновление прогресса
        self.update_state(state='PROGRESS', meta={...})

        # Парсинг главы
        content = parser.get_chapter_content(ch['url'])

        # Сохранение в БД
        save_chapter(...)
```

## Мониторинг

### Celery Flower (Web UI)

```bash
pip install flower
celery -A app.celery flower --port=5555
```

Затем откройте http://localhost:5555

### Логи

```bash
# Просмотр логов worker
journalctl -u novel-celery-worker -f

# Или если запущен вручную - смотрите stdout
```

### Redis

```bash
# Проверка очереди задач
redis-cli
> KEYS celery*
> LLEN celery  # Количество задач в очереди
```

## Troubleshooting

### Worker не запускается

```bash
# Проверьте Redis
redis-cli ping
# Должно вернуть: PONG

# Проверьте Xvfb
which xvfb-run
# Должно показать путь

# Проверьте права
ls -la start_celery_worker.sh
# Должно быть: -rwxr-xr-x
```

### Задачи висят в PENDING

```bash
# Проверьте что worker запущен
ps aux | grep celery

# Проверьте логи
tail -f /var/log/syslog | grep celery
```

### Selenium ошибки

```bash
# Убедитесь что Chrome установлен
which google-chrome

# Проверьте undetected-chromedriver
pip show undetected-chromedriver

# Проверьте Xvfb дисплей
ps aux | grep Xvfb
```

### Cloudflare блокирует

- ✅ Убедитесь что прокси работает: `curl --socks5 192.168.0.61:1080 https://czbooks.net`
- ✅ Проверьте что используется non-headless режим (`headless=False`)
- ✅ Увеличьте время ожидания Cloudflare challenge (17-20 секунд)

## Производительность

- **Concurrency**: 1 worker (czbooks требует последовательной обработки)
- **Pool**: solo (избегает проблем с Selenium в multiprocessing)
- **Скорость**: ~40 секунд на главу (включая Cloudflare challenge)
- **1362 главы**: ~15 часов полного парсинга

## Безопасность

- ✅ Celery task ID хранится в БД для отслеживания
- ✅ Автоматическая очистка task_id после завершения
- ✅ Graceful shutdown при отмене (SIGTERM)
- ✅ Timeout защита (24 часа soft limit)
- ✅ Прокси для изоляции IP адреса

## Примеры

### Тестовый парсинг 10 глав

```bash
curl -X POST http://localhost:5001/api/novels/11/parse \
  -H "Content-Type: application/json" \
  -d '{"start_chapter": 1, "max_chapters": 10}'
```

### Полный парсинг

```bash
curl -X POST http://localhost:5001/api/novels/11/parse \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Проверка статуса

```bash
curl http://localhost:5001/api/novels/11/parse/status
```

### Отмена

```bash
curl -X POST http://localhost:5001/api/novels/11/parse/cancel
```

## Заключение

Система готова к использованию! 🎉

Для запуска:

1. `sudo systemctl start redis-server`
2. `cd web_app && ./start_celery_worker.sh`
3. Запустите Flask app: `python run_web.py`
4. Используйте API endpoints для управления парсингом

Теперь парсинг czbooks.net работает в фоне через Web App! ✨
