# Анализ архитектуры Real-Time обновления UI

**Дата:** 2025-11-21
**Цель:** Определить как сделать актуальное отображение состояния кнопок в реальном времени

---

## 📊 Текущая архитектура

### 1. Используемые технологии

#### WebSocket (Flask-SocketIO)
```python
# app/__init__.py:16
socketio = SocketIO()

# app/__init__.py:124
socketio.init_app(app, cors_allowed_origins="*")
```

**Статус:** ✅ Установлен и инициализирован

#### Клиентское подключение
```javascript
// app/templates/base.html:173-186
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>

const socket = io();

socket.on('connect', function() {
    console.log('Connected to server');
});

socket.on('task_update', function(data) {
    console.log('Task update:', data);
    // Здесь можно добавить обновление UI
});
```

**Статус:** ✅ Подключен глобально в base.html

---

## 2. Существующие механизмы обновления

### A. Логи через SocketIO

**Где:** `app/services/log_service.py:60-65`

```python
def _emit_websocket(self, log_entry: LogEntry):
    """Отправка лога через WebSocket"""
    try:
        socketio.emit('log_entry', log_entry.to_dict())
    except Exception as e:
        print(f"Ошибка отправки лога через WebSocket: {e}")
```

**События:**
- `log_entry` - отправляется при каждом логе

**Проблема:** Используется только для консоли логов, не для обновления UI статусов

---

### B. Task Updates (базовая реализация)

**Где:** `app/views.py:1740-1747`

```python
def emit_task_update(task_id, progress, status, message=None):
    """Отправка обновления задачи через WebSocket"""
    socketio.emit('task_update', {
        'task_id': task_id,
        'progress': progress,
        'status': status,
        'message': message
    })
```

**Использование:**
- `app/views.py:769` - при переводе глав (старая синхронная реализация)
- `app/views.py:792` - при завершении перевода
- `app/views.py:798` - при ошибке перевода

**Проблема:** ❌ НЕ используется в Celery задачах!

---

### C. Текущие Celery задачи

**Задачи с фоновой обработкой:**

1. **`parse_novel_chapters_task`** (celery_tasks.py:58)
   - ❌ НЕ отправляет SocketIO события
   - ✅ Обновляет `novel.status`
   - ✅ Обновляет `novel.parsing_task_id`

2. **`edit_novel_chapters_task`** (celery_tasks.py:533)
   - ❌ НЕ отправляет SocketIO события
   - ✅ Обновляет `novel.status`
   - ✅ Обновляет `novel.editing_task_id`
   - ✅ Обновляет `novel.edited_chapters`

3. **`align_novel_chapters_task`** (celery_tasks.py:900+)
   - ❌ НЕ отправляет SocketIO события
   - ✅ Обновляет `novel.status`
   - ✅ Обновляет `novel.alignment_task_id`

4. **`generate_bilingual_epub_task`** (celery_tasks.py:1148)
   - ❌ НЕ отправляет SocketIO события
   - ✅ Обновляет `novel.status`
   - ✅ Обновляет `novel.epub_generation_task_id`

---

## 3. Текущий способ обновления UI

### Клиентская сторона (novel_detail.html)

**Обработчики SocketIO:** ❌ ОТСУТСТВУЮТ

**Механизм обновления:**
- Только при перезагрузке страницы (`location.reload()`)
- После отмены задачи через кнопку "Отменить"

**Пример:**
```javascript
// app/templates/novel_detail.html:758
if (data.success) {
    alert('✅ Сопоставление успешно отменено');
    location.reload(); // ← ПЕРЕЗАГРУЗКА СТРАНИЦЫ
}
```

---

## 4. Проблемы текущей архитектуры

### ❌ Проблема 1: Отсутствие Real-Time обновлений

**Симптомы:**
- Кнопки не обновляются автоматически
- Статусы не меняются без перезагрузки
- Прогресс не отображается в реальном времени

**Причина:**
- Celery задачи НЕ отправляют события через SocketIO
- Страница `novel_detail.html` НЕ слушает события SocketIO

---

### ❌ Проблема 2: Разделенные контексты

```
┌─────────────────┐
│  Celery Worker  │
│  (отдельный     │
│   процесс)      │
└────────┬────────┘
         │ ❌ НЕТ прямого доступа к socketio
         │
         ▼
    ┌────────────┐
    │  PostgreSQL│ ← Обновляет novel.status
    └────────────┘
         ▲
         │
┌────────┴────────┐
│  Flask App      │
│  (веб-сервер)   │
└────────┬────────┘
         │
         ▼
    ┌────────────┐
    │  SocketIO  │ ← НЕ получает обновлений от Celery
    └────────────┘
```

**Проблема:** Celery worker работает в отдельном процессе и не имеет прямого доступа к Flask SocketIO instance.

---

## 5. Существующие паттерны в других проектах

### Паттерн 1: Celery + Redis Pub/Sub + SocketIO

```python
# В Celery задаче
redis_client.publish('task_updates', json.dumps({
    'task_id': task_id,
    'status': 'progress',
    'data': {...}
}))

# Во Flask app (отдельный поток)
def redis_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('task_updates')
    for message in pubsub.listen():
        socketio.emit('task_update', message['data'])
```

**Плюсы:**
- ✅ Реальное разделение ответственности
- ✅ Масштабируемость
- ✅ Надежность

**Минусы:**
- ⚠️ Требует дополнительного Redis Pub/Sub канала
- ⚠️ Нужен отдельный listener поток во Flask

---

### Паттерн 2: Периодический polling через AJAX

```javascript
// Клиент опрашивает сервер каждые N секунд
setInterval(async function() {
    const response = await fetch(`/api/novels/${novelId}/status`);
    const data = await response.json();
    updateUI(data);
}, 3000);
```

**Плюсы:**
- ✅ Простая реализация
- ✅ Не требует WebSocket

**Минусы:**
- ⚠️ Задержка до 3 секунд
- ⚠️ Лишние HTTP запросы

---

### Паттерн 3: Server-Sent Events (SSE)

```python
@app.route('/api/novels/<int:novel_id>/events')
def novel_events(novel_id):
    def generate():
        while True:
            novel = Novel.query.get(novel_id)
            yield f"data: {json.dumps(novel.status)}\n\n"
            time.sleep(2)
    return Response(generate(), mimetype='text/event-stream')
```

**Плюсы:**
- ✅ Простой протокол
- ✅ Автоматическое переподключение

**Минусы:**
- ⚠️ Только server → client
- ⚠️ Не работает с некоторыми прокси

---

## 6. Рекомендуемое решение для этого проекта

### Вариант A: Polling через AJAX (БЫСТРАЯ РЕАЛИЗАЦИЯ)

**Рекомендую этот вариант для MVP!**

#### Преимущества:
- ✅ Не требует изменений в Celery
- ✅ Не требует Redis Pub/Sub
- ✅ Работает с существующей архитектурой
- ✅ Быстрая реализация (30 минут)

#### Архитектура:

```javascript
// В novel_detail.html
let statusCheckInterval = null;

function startStatusPolling(novelId) {
    statusCheckInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/novels/${novelId}/status`);
            const data = await response.json();

            // Обновляем UI на основе статуса
            updateNovelStatus(data);

            // Останавливаем polling если задача завершена
            if (!data.has_active_tasks) {
                stopStatusPolling();
            }
        } catch (error) {
            console.error('Error polling status:', error);
        }
    }, 2000); // Каждые 2 секунды
}

function updateNovelStatus(data) {
    // Обновление кнопок и статусов
    if (data.epub_generation_task_id) {
        // Блокируем кнопку, показываем спиннер
        document.querySelector('#epub-btn').disabled = true;
        document.querySelector('#epub-status').textContent = 'Генерируется...';
    } else if (data.status === 'epub_generated') {
        // Разблокируем, показываем кнопку скачивания
        document.querySelector('#epub-btn').disabled = false;
        document.querySelector('#download-btn').style.display = 'block';
    }

    // Аналогично для других задач...
}
```

#### Нужно добавить:

1. **API Endpoint** для получения статуса:
```python
@api_bp.route('/novels/<int:novel_id>/status')
def get_novel_status(novel_id):
    novel = Novel.query.get_or_404(novel_id)

    return jsonify({
        'id': novel.id,
        'status': novel.status,

        # Парсинг
        'parsing_task_id': novel.parsing_task_id,
        'parsed_chapters': novel.parsed_chapters,
        'total_chapters': novel.total_chapters,

        # Редактура
        'editing_task_id': novel.editing_task_id,
        'edited_chapters': novel.edited_chapters,

        # Выравнивание
        'alignment_task_id': novel.alignment_task_id,
        'aligned_chapters': novel.aligned_chapters,

        # EPUB генерация
        'epub_generation_task_id': novel.epub_generation_task_id,
        'epub_path': novel.epub_path,

        # Есть ли активные задачи
        'has_active_tasks': any([
            novel.parsing_task_id,
            novel.editing_task_id,
            novel.alignment_task_id,
            novel.epub_generation_task_id
        ])
    })
```

2. **JavaScript в novel_detail.html:**
```javascript
document.addEventListener('DOMContentLoaded', function() {
    const novelId = {{ novel.id }};

    // Проверяем есть ли активные задачи
    {% if novel.parsing_task_id or novel.editing_task_id or novel.alignment_task_id or novel.epub_generation_task_id %}
    startStatusPolling(novelId);
    {% endif %}
});
```

---

### Вариант B: Redis Pub/Sub + SocketIO (ПОЛНОЦЕННОЕ РЕШЕНИЕ)

**Рекомендую для production после MVP!**

#### Преимущества:
- ✅ Настоящий real-time (задержка < 100ms)
- ✅ Масштабируемость
- ✅ Меньше нагрузки на БД

#### Архитектура:

```
┌─────────────────┐
│  Celery Worker  │
│                 │
│  1. Обновляет   │
│     novel.status│
│                 │
│  2. Публикует   │
│     в Redis:    │
│     PUBLISH     │
│     "updates"   │
│     {...}       │
└────────┬────────┘
         │
         ▼
    ┌────────────┐
    │   Redis    │ ← Pub/Sub канал "updates"
    │  Pub/Sub   │
    └─────┬──────┘
          │
          ▼
    ┌────────────┐
    │ Flask App  │
    │            │
    │ Listener   │ ← Слушает канал "updates"
    │  Thread    │
    └─────┬──────┘
          │
          ▼
    ┌────────────┐
    │  SocketIO  │ ← Отправляет на клиент
    └────────────┘
          │
          ▼
    ┌────────────┐
    │  Browser   │ ← Обновляет UI мгновенно
    └────────────┘
```

#### Реализация:

**1. В Celery задаче:**
```python
# app/celery_tasks.py
def publish_task_update(novel_id, update_data):
    """Публикация обновления в Redis Pub/Sub"""
    import redis
    redis_client = redis.Redis(host='localhost', port=6379, db=1)

    message = json.dumps({
        'novel_id': novel_id,
        'timestamp': time.time(),
        **update_data
    })

    redis_client.publish('novel_updates', message)

# В задаче генерации EPUB
def generate_bilingual_epub_task(self, novel_id):
    # ...
    novel.status = 'generating_epub'
    db.session.commit()

    # Отправляем обновление
    publish_task_update(novel_id, {
        'type': 'epub_generation',
        'status': 'generating_epub',
        'progress': 0
    })

    # ... генерация ...

    # Обновляем прогресс
    publish_task_update(novel_id, {
        'type': 'epub_generation',
        'status': 'generating_epub',
        'progress': 50
    })
```

**2. Listener в Flask app:**
```python
# app/__init__.py
def start_redis_listener(app):
    """Запуск listener для Redis Pub/Sub"""
    import redis
    import threading
    import json

    def listen():
        redis_client = redis.Redis(host='localhost', port=6379, db=1)
        pubsub = redis_client.pubsub()
        pubsub.subscribe('novel_updates')

        with app.app_context():
            for message in pubsub.listen():
                if message['type'] == 'message':
                    data = json.loads(message['data'])

                    # Отправляем через SocketIO
                    socketio.emit('novel_update', data)

    thread = threading.Thread(target=listen, daemon=True)
    thread.start()

# В create_app()
start_redis_listener(app)
```

**3. Клиент в novel_detail.html:**
```javascript
const socket = io();

socket.on('novel_update', function(data) {
    if (data.novel_id === {{ novel.id }}) {
        updateNovelStatus(data);
    }
});

function updateNovelStatus(data) {
    if (data.type === 'epub_generation') {
        const epubBtn = document.querySelector('#epub-generation-btn');
        const epubStatus = document.querySelector('#epub-status');

        if (data.status === 'generating_epub') {
            epubBtn.disabled = true;
            epubBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Генерируется...';
            epubStatus.textContent = `Прогресс: ${data.progress}%`;
        } else if (data.status === 'epub_generated') {
            epubBtn.disabled = false;
            epubBtn.innerHTML = '<i class="bi bi-book"></i> Двуязычный EPUB';

            // Показываем кнопку скачивания
            const downloadBtn = document.querySelector('#epub-download-btn');
            downloadBtn.style.display = 'block';
        }
    }

    // Аналогично для других типов задач
}
```

---

## 7. Сравнение решений

| Критерий | Polling (AJAX) | Redis Pub/Sub + SocketIO |
|----------|----------------|--------------------------|
| **Скорость реализации** | 30 минут | 2-3 часа |
| **Задержка обновления** | 2 секунды | < 100 мс |
| **Нагрузка на сервер** | Средняя (запросы каждые 2с) | Низкая (события по факту) |
| **Масштабируемость** | Ограниченная | Отличная |
| **Сложность** | Низкая | Средняя |
| **Надежность** | Средняя | Высокая |
| **Production-ready** | Да (для MVP) | Да (для финала) |

---

## 8. Итоговая рекомендация

### Этап 1: MVP (СЕЙЧАС) - Polling через AJAX
- Реализовать polling для `novel_detail.html`
- Добавить API endpoint `/api/novels/<id>/status`
- Обновлять UI каждые 2 секунды

**Время:** 30-60 минут
**Достаточно для:** Демо и тестирования

### Этап 2: Production (ПОТОМ) - Redis Pub/Sub
- Добавить Redis Pub/Sub listener
- Интегрировать отправку событий в Celery задачи
- Обновлять UI мгновенно через SocketIO

**Время:** 2-3 часа
**Достаточно для:** Production использования

---

## 9. План реализации (Этап 1 - Polling)

### Шаг 1: Создать API endpoint
```bash
# Создать: app/api/novels.py (расширить существующий)
@api_bp.route('/novels/<int:novel_id>/status')
def get_novel_status(novel_id):
    # ... (см. выше)
```

### Шаг 2: Добавить JavaScript в novel_detail.html
```javascript
// Функции polling
function startStatusPolling(novelId) { ... }
function stopStatusPolling() { ... }
function updateNovelStatus(data) { ... }
```

### Шаг 3: Обновить UI элементы
- Добавить `id` к кнопкам и статусам
- Добавить функции обновления DOM

### Шаг 4: Тестирование
- Запустить генерацию EPUB
- Проверить что кнопка блокируется
- Проверить что статус обновляется каждые 2 секунды

---

## 10. Примеры кода для немедленной реализации

### Файл: `app/api/novels.py` (добавить в конец)

```python
@api_bp.route('/novels/<int:novel_id>/status')
def get_novel_status(novel_id):
    """Получение текущего статуса новеллы для real-time обновлений"""
    novel = Novel.query.get_or_404(novel_id)

    return jsonify({
        'success': True,
        'novel': {
            'id': novel.id,
            'status': novel.status,
            'title': novel.title,

            # Статистика
            'total_chapters': novel.total_chapters,
            'parsed_chapters': novel.parsed_chapters,
            'translated_chapters': novel.translated_chapters,
            'edited_chapters': novel.edited_chapters,
            'aligned_chapters': novel.aligned_chapters,

            # Активные задачи
            'parsing_task_id': novel.parsing_task_id,
            'editing_task_id': novel.editing_task_id,
            'alignment_task_id': novel.alignment_task_id,
            'epub_generation_task_id': novel.epub_generation_task_id,

            # EPUB
            'epub_path': novel.epub_path,

            # Флаг активных задач
            'has_active_tasks': bool(
                novel.parsing_task_id or
                novel.editing_task_id or
                novel.alignment_task_id or
                novel.epub_generation_task_id
            )
        }
    })
```

### Файл: `app/templates/novel_detail.html` (добавить в конец блока script)

```javascript
// Real-time status polling
let statusPollingInterval = null;

function startStatusPolling() {
    const novelId = {{ novel.id }};

    statusPollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/novels/${novelId}/status`);
            const data = await response.json();

            if (data.success) {
                updateNovelUI(data.novel);

                // Останавливаем polling если нет активных задач
                if (!data.novel.has_active_tasks) {
                    stopStatusPolling();
                }
            }
        } catch (error) {
            console.error('Ошибка polling статуса:', error);
        }
    }, 2000); // Каждые 2 секунды
}

function stopStatusPolling() {
    if (statusPollingInterval) {
        clearInterval(statusPollingInterval);
        statusPollingInterval = null;
    }
}

function updateNovelUI(novel) {
    // Обновление EPUB генерации
    const epubBtn = document.querySelector('#epub-generation-btn');
    const epubStatus = document.querySelector('#epub-status-alert');
    const epubDownloadBtn = document.querySelector('#epub-download-btn');

    if (novel.epub_generation_task_id) {
        // Генерация в процессе
        if (epubBtn) {
            epubBtn.disabled = true;
            epubBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Генерируется...';
        }

        if (epubStatus) {
            epubStatus.style.display = 'block';
            epubStatus.className = 'alert alert-warning mt-3';
        }
    } else if (novel.status === 'epub_generated' && novel.epub_path) {
        // Генерация завершена
        if (epubBtn) {
            epubBtn.disabled = false;
            epubBtn.innerHTML = '<i class="bi bi-book"></i> Двуязычный EPUB (RU + 中文)';
        }

        if (epubStatus) {
            epubStatus.style.display = 'block';
            epubStatus.className = 'alert alert-success mt-3';
        }

        if (epubDownloadBtn) {
            epubDownloadBtn.style.display = 'inline-block';
        }

        // Перезагружаем страницу один раз когда всё готово
        if (statusPollingInterval) {
            stopStatusPolling();
            location.reload();
        }
    }

    // TODO: Аналогично для parsing, editing, alignment
}

// Запуск polling при загрузке страницы если есть активные задачи
document.addEventListener('DOMContentLoaded', function() {
    {% if novel.parsing_task_id or novel.editing_task_id or novel.alignment_task_id or novel.epub_generation_task_id %}
    startStatusPolling();
    {% endif %}
});

// Остановка polling при закрытии страницы
window.addEventListener('beforeunload', function() {
    stopStatusPolling();
});
```

---

## Заключение

**Рекомендую начать с Варианта A (Polling):**
- ✅ Быстрая реализация
- ✅ Достаточно для MVP
- ✅ Работает с текущей архитектурой
- ✅ Не требует изменений в Celery

**После MVP перейти на Вариант B (Redis Pub/Sub):**
- ✅ Настоящий real-time
- ✅ Лучшая производительность
- ✅ Production-ready

**Время реализации:**
- Вариант A: 30-60 минут
- Вариант B: 2-3 часа
