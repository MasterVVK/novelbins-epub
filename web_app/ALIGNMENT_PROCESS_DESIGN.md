# Дизайн процесса билингвального выравнивания

## Анализ текущей реализации редактирования

### 1. Архитектура редактирования глав

#### 1.1 Модель Novel (`app/models/novel.py:48-50`)
```python
# Celery task ID для отслеживания фоновых задач
parsing_task_id = Column(String(255))  # ID задачи Celery для парсинга
editing_task_id = Column(String(255))  # ID задачи Celery для редактуры

# Статистика
edited_chapters = Column(Integer, default=0)
```

#### 1.2 UI кнопка (`novel_detail.html:152-164`)
```html
<div class="col-md-3 mb-2">
    {% if novel.editing_task_id %}
        <button type="button" class="btn btn-outline-danger w-100" onclick="cancelEditing({{ novel.id }})">
            <i class="bi bi-x-circle"></i> Отменить редактуру
        </button>
    {% else %}
        <form method="POST" action="{{ url_for('main.start_editing', novel_id=novel.id) }}" style="display: inline;">
            <button type="submit" class="btn btn-outline-warning w-100">
                <i class="bi bi-pencil-square"></i> Редактура
            </button>
        </form>
    {% endif %}
</div>
```

**Ключевые особенности**:
- ✅ Условная кнопка: "Редактура" → "Отменить редактуру" в зависимости от `editing_task_id`
- ✅ POST форма для запуска процесса
- ✅ JavaScript функция для отмены
- ✅ Иконки Bootstrap Icons
- ✅ Цветовое кодирование (outline-warning для редактуры, outline-danger для отмены)

#### 1.3 API endpoint запуска (`views.py:798-878`)
```python
@main_bp.route('/novels/<int:novel_id>/start-editing', methods=['POST'])
def start_editing(novel_id):
    """Запуск редактуры новеллы через Celery"""
    novel = Novel.query.get_or_404(novel_id)

    # IDEMPOTENCY CHECK: Проверяем, не запущена ли уже редактура
    if novel.editing_task_id:
        task_result = AsyncResult(novel.editing_task_id, app=celery)
        if task_result.state in ['PENDING', 'STARTED', 'PROGRESS']:
            flash('Редактура уже запущена', 'warning')
            return redirect(...)

    # Получаем главы для редактуры
    chapters = Chapter.query.filter_by(
        novel_id=novel_id,
        status='translated',  # Только переведенные главы
    ).order_by(Chapter.chapter_number).all()

    # Запускаем Celery задачу
    task = edit_novel_chapters_task.apply_async(
        kwargs={
            'novel_id': novel_id,
            'chapter_ids': chapter_ids,
            'parallel_threads': parallel_threads
        },
        queue='czbooks_queue'
    )

    # Сохраняем task_id
    novel.editing_task_id = task.id
    db.session.commit()

    flash('Редактура запущена', 'success')
    return redirect(url_for('main.novel_detail', novel_id=novel_id))
```

**Ключевые особенности**:
- ✅ Проверка идемпотентности (не запускать дублирующую задачу)
- ✅ Фильтрация глав по статусу (`status='translated'`)
- ✅ Сохранение `task_id` в БД для отслеживания
- ✅ Параллельные потоки из конфига новеллы
- ✅ Flash сообщения для пользователя

#### 1.4 Celery задача (`celery_tasks.py:531-858`)
```python
@celery.task(bind=True, base=CallbackTask, soft_time_limit=172800, time_limit=172800)
def edit_novel_chapters_task(self, novel_id, chapter_ids, parallel_threads=3):
    """Фоновая задача редактуры глав новеллы"""

    # Обновляем статус новеллы
    novel.status = 'editing'
    novel.editing_task_id = self.request.id
    db.session.commit()

    # Параллельная обработка через ThreadPoolExecutor
    def edit_single_chapter(chapter_id):
        with app.app_context():
            chapter = Chapter.query.get(chapter_id)

            # ЗАЩИТА ОТ ДУБЛИРОВАНИЯ
            if chapter.status == 'edited':
                return True  # Уже отредактирована

            # Редактирование
            editor_service.edit_chapter(chapter)

            # Обновление статуса
            chapter.status = 'edited'
            db.session.commit()

            # Обновление счётчика (thread-safe)
            with counter_lock:
                novel.edited_chapters += 1
                db.session.commit()

    # Запуск параллельных потоков
    with ThreadPoolExecutor(max_workers=parallel_threads) as executor:
        futures = {executor.submit(edit_single_chapter, ch_id): ch_id
                   for ch_id in chapter_ids}

        for future in as_completed(futures):
            # Обновление прогресса
            self.update_state(state='PROGRESS', meta={
                'status': f'Обработано {processed_count}/{total_chapters}',
                'progress': int((processed_count / total_chapters) * 100)
            })

    # Финальный статус
    novel.status = 'completed' if success_count == total_chapters else 'partial'
    novel.editing_task_id = None
    db.session.commit()
```

**Ключевые особенности**:
- ✅ Параллельная обработка глав через `ThreadPoolExecutor`
- ✅ Отдельный Flask `app_context()` для каждого потока
- ✅ Thread-safe обновление счётчиков через `Lock()`
- ✅ Защита от дублирования (проверка `chapter.status == 'edited'`)
- ✅ Real-time обновление прогресса через `update_state()`
- ✅ Очистка `editing_task_id` после завершения

#### 1.5 Отмена задачи (`views.py` + JavaScript)
```python
# API endpoint
@main_bp.route('/novels/<int:novel_id>/cancel-editing', methods=['POST'])
def cancel_editing(novel_id):
    novel = Novel.query.get_or_404(novel_id)

    if novel.editing_task_id:
        celery.control.revoke(novel.editing_task_id, terminate=True, signal='SIGTERM')
        novel.editing_task_id = None
        novel.status = 'editing_cancelled'
        db.session.commit()

    return jsonify({'success': True})

# JavaScript (novel_detail.html)
function cancelEditing(novelId) {
    if (confirm('Отменить редактуру?')) {
        fetch(`/novels/${novelId}/cancel-editing`, {method: 'POST'})
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                }
            });
    }
}
```

---

## 2. Предлагаемый дизайн процесса выравнивания

### 2.1 Изменения в модели Novel

**Добавить поля** (`app/models/novel.py`):
```python
# Celery task ID для отслеживания фоновых задач
parsing_task_id = Column(String(255))
editing_task_id = Column(String(255))
alignment_task_id = Column(String(255))  # ← НОВОЕ

# Статистика
total_chapters = Column(Integer, default=0)
parsed_chapters = Column(Integer, default=0)
translated_chapters = Column(Integer, default=0)
edited_chapters = Column(Integer, default=0)
aligned_chapters = Column(Integer, default=0)  # ← НОВОЕ

# Добавить property для прогресса
@property
def alignment_progress_percentage(self):
    """Процент завершения выравнивания"""
    if self.total_chapters == 0:
        return 0
    return round((self.aligned_chapters / self.total_chapters) * 100, 1)
```

**Миграция**:
```bash
cd web_app
flask db migrate -m "Add alignment_task_id and aligned_chapters to Novel"
flask db upgrade
```

### 2.2 UI дизайн кнопки

**Расположение**: `novel_detail.html` секция "Действия" (после кнопки EPUB)

**Вариант 1: В первой строке (между Редактура и EPUB)**
```html
<!-- Текущая структура -->
<div class="row">
    <div class="col-md-3 mb-2"><!-- Парсинг --></div>
    <div class="col-md-3 mb-2"><!-- Перевод --></div>
    <div class="col-md-3 mb-2"><!-- Редактура --></div>
    <div class="col-md-3 mb-2"><!-- EPUB --></div>
</div>

<!-- Новая структура: 5 кнопок в ряд -->
<div class="row">
    <div class="col-md-2 mb-2"><!-- Парсинг --></div>
    <div class="col-md-2 mb-2"><!-- Перевод --></div>
    <div class="col-md-2 mb-2"><!-- Редактура --></div>
    <div class="col-md-3 mb-2"><!-- Выравнивание ← НОВОЕ --></div>
    <div class="col-md-3 mb-2"><!-- EPUB --></div>
</div>
```

**Вариант 2: Во второй строке (рекомендуемый) ✅**
```html
<!-- Первая строка: основные операции (без изменений) -->
<div class="row">
    <div class="col-md-3 mb-2"><!-- Парсинг --></div>
    <div class="col-md-3 mb-2"><!-- Перевод --></div>
    <div class="col-md-3 mb-2"><!-- Редактура --></div>
    <div class="col-md-3 mb-2"><!-- EPUB --></div>
</div>

<!-- Вторая строка: дополнительные опции -->
<div class="row mt-2">
    <div class="col-md-6 mb-2">
        <!-- Выравнивание ← НОВОЕ -->
        {% if novel.alignment_task_id %}
            <button type="button" class="btn btn-outline-danger w-100" onclick="cancelAlignment({{ novel.id }})">
                <i class="bi bi-x-circle"></i> Отменить выравнивание
            </button>
        {% else %}
            <form method="POST" action="{{ url_for('main.start_alignment', novel_id=novel.id) }}" style="display: inline;">
                <button type="submit" class="btn btn-outline-info w-100">
                    <i class="bi bi-diagram-3"></i> Билингвальное выравнивание
                </button>
            </form>
        {% endif %}
    </div>
    <div class="col-md-6 mb-2">
        <!-- Двуязычный EPUB -->
        <form method="POST" action="{{ url_for('main.generate_bilingual_epub', novel_id=novel.id) }}" style="display: inline;">
            <button type="submit" class="btn btn-outline-secondary w-100">
                <i class="bi bi-book"></i> Двуязычный EPUB (RU + 中文)
            </button>
        </form>
    </div>
</div>
```

**Преимущества варианта 2**:
- ✅ Не меняет существующую раскладку 4 основных кнопок
- ✅ Группирует билингвальные функции вместе (выравнивание + двуязычный EPUB)
- ✅ Логичный порядок: сначала выровнять, потом создать EPUB
- ✅ Больше места для текста на кнопках (col-md-6 вместо col-md-2)

**Выбор иконок**:
- `bi-diagram-3` - узлы и связи (выравнивание структуры) ✅ **Рекомендуется**
- `bi-arrows-angle-contract` - стрелки сближения (сопоставление)
- `bi-translate` - перевод (но уже используется для "Перевод")
- `bi-link-45deg` - связь между элементами

**Цветовая схема**:
- Запуск: `btn-outline-info` (голубой) - ассоциация с информацией/данными
- Отмена: `btn-outline-danger` (красный) - как у всех других отмен

### 2.3 API Endpoints

**Создать 3 новых endpoint** (`app/views.py`):

#### 2.3.1 Запуск выравнивания
```python
@main_bp.route('/novels/<int:novel_id>/start-alignment', methods=['POST'])
def start_alignment(novel_id):
    """Запуск билингвального выравнивания новеллы через Celery"""
    logger.info(f"🚀 Запрос на выравнивание новеллы {novel_id}")
    novel = Novel.query.get_or_404(novel_id)

    # IDEMPOTENCY CHECK
    if novel.alignment_task_id:
        from celery.result import AsyncResult
        task_result = AsyncResult(novel.alignment_task_id, app=celery)

        if task_result.state in ['PENDING', 'STARTED', 'PROGRESS']:
            logger.warning(f"⚠️ Выравнивание уже запущено (task_id: {novel.alignment_task_id})")
            flash(f'Выравнивание уже запущено (задача: {novel.alignment_task_id[:8]}...)', 'warning')
            return redirect(url_for('main.novel_detail', novel_id=novel_id))
        else:
            logger.info(f"✅ Предыдущая задача завершена (state: {task_result.state}), запускаем новую")
            novel.alignment_task_id = None
            db.session.commit()

    # Получаем главы для выравнивания
    # ВАЖНО: Выравнивание требует наличия и chinese_text и russian_text
    chapters = Chapter.query.filter(
        Chapter.novel_id == novel_id,
        Chapter.original_text.isnot(None),  # Есть китайский оригинал
        Chapter.original_text != '',
    ).filter(
        # Есть хотя бы один из переводов
        db.or_(
            Chapter.current_translation.has(),
            Chapter.edited_translation.has()
        )
    ).order_by(Chapter.chapter_number).all()

    logger.info(f"🔍 Найдено глав для выравнивания: {len(chapters)}")

    if not chapters:
        logger.warning("❌ Нет глав для выравнивания (нужны главы с оригиналом и переводом)")
        flash('Нет глав для выравнивания. Требуются главы с китайским оригиналом и переводом.', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Получаем настройку количества потоков
    parallel_threads = 3  # По умолчанию
    if novel.config:
        parallel_threads = novel.config.get('alignment_threads', 3)

    # Запускаем Celery задачу
    try:
        from app.celery_tasks import align_novel_chapters_task

        chapter_ids = [ch.id for ch in chapters]
        task = align_novel_chapters_task.apply_async(
            kwargs={
                'novel_id': novel_id,
                'chapter_ids': chapter_ids,
                'parallel_threads': parallel_threads
            },
            queue='czbooks_queue'
        )

        # Сохраняем task_id
        novel.alignment_task_id = task.id
        db.session.commit()

        logger.info(f"✅ Task ID: {task.id}, State: {task.state}")
        LogService.log_info(
            f"🎯 Выравнивание запущено через Celery для {len(chapters)} глав (потоков: {parallel_threads})",
            novel_id=novel_id
        )

        flash(f'Запущено выравнивание {len(chapters)} глав с {parallel_threads} потоками', 'success')

    except Exception as e:
        logger.error(f"❌ Ошибка запуска выравнивания: {e}")
        flash(f'Ошибка запуска выравнивания: {e}', 'danger')

    return redirect(url_for('main.novel_detail', novel_id=novel_id))
```

#### 2.3.2 Отмена выравнивания
```python
@main_bp.route('/novels/<int:novel_id>/cancel-alignment', methods=['POST'])
def cancel_alignment(novel_id):
    """Отмена билингвального выравнивания"""
    logger.info(f"🛑 Запрос на отмену выравнивания новеллы {novel_id}")
    novel = Novel.query.get_or_404(novel_id)

    if novel.alignment_task_id:
        from celery.control import revoke

        logger.info(f"🛑 Отменяем задачу выравнивания: {novel.alignment_task_id}")
        revoke(novel.alignment_task_id, terminate=True, signal='SIGTERM')

        # Обновляем статус
        novel.alignment_task_id = None
        novel.status = 'alignment_cancelled'
        db.session.commit()

        LogService.log_warning(
            f"🛑 Выравнивание отменено пользователем",
            novel_id=novel_id
        )

        return jsonify({'success': True, 'message': 'Выравнивание отменено'})

    return jsonify({'success': False, 'message': 'Нет активной задачи выравнивания'})
```

#### 2.3.3 JavaScript для отмены
```javascript
// novel_detail.html
function cancelAlignment(novelId) {
    if (confirm('Вы уверены, что хотите отменить выравнивание? Прогресс будет сохранён.')) {
        fetch(`/novels/${novelId}/cancel-alignment`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Выравнивание отменено');
                location.reload();
            } else {
                alert('Ошибка: ' + data.message);
            }
        })
        .catch(error => {
            alert('Ошибка отмены: ' + error);
        });
    }
}
```

### 2.4 Celery задача

**Создать** `align_novel_chapters_task` (`app/celery_tasks.py`):

```python
@celery.task(bind=True, base=CallbackTask, soft_time_limit=172800, time_limit=172800)  # 48 часов
def align_novel_chapters_task(self, novel_id, chapter_ids, parallel_threads=3):
    """
    Фоновая задача билингвального выравнивания глав новеллы

    Args:
        novel_id: ID новеллы
        chapter_ids: Список ID глав для выравнивания
        parallel_threads: Количество параллельных потоков (из конфига новеллы)
    """
    from app.services.bilingual_alignment_service import BilingualAlignmentService
    from app.services.log_service import LogService
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock

    # Флаг для отслеживания отмены
    global _cancel_requested
    _cancel_requested = False

    # Устанавливаем обработчик сигнала SIGTERM
    old_handler = signal.signal(signal.SIGTERM, signal_handler)

    # Блокировка для thread-safe доступа к счётчикам
    counter_lock = Lock()

    try:
        # Получаем новеллу
        novel = Novel.query.get(novel_id)
        if not novel:
            raise ValueError(f"Novel {novel_id} not found")

        # Обновляем статус
        novel.status = 'aligning'
        novel.alignment_task_id = self.request.id
        db.session.commit()

        # Получаем настройку потоков из конфига новеллы
        if novel.config:
            parallel_threads = novel.config.get('alignment_threads', parallel_threads)

        # Инициализируем сервис выравнивания
        # Используем template_id и model_id из новеллы
        alignment_service = BilingualAlignmentService(
            template_id=novel.bilingual_template_id,
            model_id=None  # Будет взят из шаблона
        )

        # Получаем главы
        from app.models import Chapter
        chapters = Chapter.query.filter(Chapter.id.in_(chapter_ids)).order_by(Chapter.chapter_number).all()

        if not chapters:
            raise ValueError("Главы не найдены")

        total_chapters = len(chapters)
        success_count = 0
        processed_count = 0

        self.update_state(state='PROGRESS', meta={'status': 'Начинаем выравнивание', 'progress': 0})
        LogService.log_info(
            f"🔗 [Novel:{novel_id}] Начинаем билингвальное выравнивание {total_chapters} глав(ы) в {parallel_threads} потоков",
            novel_id=novel_id
        )

        # Функция для выравнивания одной главы в отдельном потоке
        def align_single_chapter(chapter_id):
            nonlocal success_count, processed_count

            # Каждый поток создает свою Flask app context и сессию БД
            from app import create_app
            app = create_app()

            with app.app_context():
                # Загружаем главу и новеллу в контексте текущего потока
                from app.models import Chapter, Novel
                from app.models.bilingual_alignment import BilingualAlignment

                chapter = Chapter.query.get(chapter_id)
                if not chapter:
                    return False

                # ЗАЩИТА ОТ ДУБЛИРОВАНИЯ: Проверяем, не выровнена ли уже глава
                existing_alignment = BilingualAlignment.query.filter_by(chapter_id=chapter_id).first()
                if existing_alignment:
                    LogService.log_info(
                        f"✅ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Выравнивание уже существует (пропускаем)",
                        novel_id=novel_id,
                        chapter_id=chapter_id
                    )
                    with counter_lock:
                        processed_count += 1
                        success_count += 1
                    return True

                # Проверка отмены задачи
                novel_fresh = Novel.query.get(novel_id)
                if _cancel_requested or novel_fresh.status == 'alignment_cancelled':
                    LogService.log_warning(
                        f"🛑 [Novel:{novel_id}, Ch:{chapter.chapter_number}] Выравнивание отменено",
                        novel_id=novel_id,
                        chapter_id=chapter_id
                    )
                    return False

                try:
                    # Создаём сервис в контексте потока
                    service = BilingualAlignmentService(
                        template_id=novel_fresh.bilingual_template_id,
                        model_id=None
                    )

                    LogService.log_info(
                        f"🔗 [Novel:{novel_id}, Ch:{chapter.chapter_number}] Начинаем выравнивание",
                        novel_id=novel_id,
                        chapter_id=chapter_id
                    )

                    start_time = datetime.now()

                    # ВЫРАВНИВАНИЕ ГЛАВЫ
                    alignments = service.align_chapter(
                        chapter=chapter,
                        force_refresh=False,  # Не пересоздавать если есть
                        save_to_cache=True
                    )

                    duration = (datetime.now() - start_time).total_seconds()

                    if alignments:
                        # Обновляем счётчик в новелле (thread-safe)
                        with counter_lock:
                            novel_fresh.aligned_chapters = Novel.query.get(novel_id).aligned_chapters + 1
                            db.session.commit()
                            processed_count += 1
                            success_count += 1

                        LogService.log_info(
                            f"✅ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Выравнивание завершено за {duration:.1f}с ({len(alignments)} пар)",
                            novel_id=novel_id,
                            chapter_id=chapter_id
                        )
                        return True
                    else:
                        LogService.log_error(
                            f"❌ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Выравнивание вернуло пустой результат",
                            novel_id=novel_id,
                            chapter_id=chapter_id
                        )
                        with counter_lock:
                            processed_count += 1
                        return False

                except Exception as e:
                    LogService.log_error(
                        f"❌ [Novel:{novel_id}, Ch:{chapter.chapter_number}] Ошибка выравнивания: {e}",
                        novel_id=novel_id,
                        chapter_id=chapter_id
                    )
                    with counter_lock:
                        processed_count += 1
                    return False

        # Параллельное выравнивание глав
        LogService.log_info(
            f"🚀 [Novel:{novel_id}] Запускаем {parallel_threads} потоков для выравнивания {total_chapters} глав",
            novel_id=novel_id
        )

        with ThreadPoolExecutor(max_workers=parallel_threads) as executor:
            # Запускаем задачи
            futures = {executor.submit(align_single_chapter, ch_id): ch_id
                      for ch_id in chapter_ids}

            # Обрабатываем результаты по мере выполнения
            for future in as_completed(futures):
                chapter_id = futures[future]

                try:
                    result = future.result()

                    # Обновляем прогресс
                    progress = int((processed_count / total_chapters) * 100)
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'status': f'Обработано {processed_count}/{total_chapters} глав',
                            'progress': progress,
                            'success_count': success_count,
                            'processed_count': processed_count
                        }
                    )

                    # Логируем прогресс каждые 10%
                    if processed_count % max(1, total_chapters // 10) == 0:
                        LogService.log_info(
                            f"📊 [Novel:{novel_id}] Прогресс выравнивания: {processed_count}/{total_chapters} ({progress}%) | Успешно: {success_count}",
                            novel_id=novel_id
                        )

                except Exception as e:
                    LogService.log_error(
                        f"❌ [Novel:{novel_id}] Ошибка в потоке выравнивания: {e}",
                        novel_id=novel_id
                    )

        # Финальный статус
        if success_count == total_chapters:
            novel.status = 'completed'
            LogService.log_info(
                f"✅ [Novel:{novel_id}] Выравнивание завершено успешно: {success_count}/{total_chapters} глав",
                novel_id=novel_id
            )
        else:
            novel.status = 'partial_alignment'
            LogService.log_warning(
                f"⚠️ [Novel:{novel_id}] Выравнивание завершено частично: {success_count}/{total_chapters} глав",
                novel_id=novel_id
            )

        novel.alignment_task_id = None
        db.session.commit()

        return {
            'status': 'completed',
            'total': total_chapters,
            'success': success_count,
            'failed': total_chapters - success_count
        }

    except Exception as e:
        LogService.log_error(f"❌ [Novel:{novel_id}] Критическая ошибка выравнивания: {e}", novel_id=novel_id)

        # Обновляем статус на ошибку
        novel = Novel.query.get(novel_id)
        if novel:
            novel.status = 'alignment_error'
            novel.alignment_task_id = None
            db.session.commit()

        raise

    finally:
        # Восстанавливаем старый обработчик сигнала
        signal.signal(signal.SIGTERM, old_handler)
```

### 2.5 Отображение прогресса

**Добавить секцию прогресса** в `novel_detail.html` (после статистики):

```html
<!-- Прогресс выравнивания -->
{% if novel.alignment_task_id %}
<div class="mt-3">
    <div class="alert alert-info">
        <div class="d-flex justify-content-between align-items-center">
            <div>
                <i class="bi bi-diagram-3"></i>
                <strong>Выравнивание:</strong>
                Выравниваем главы...
                <span id="alignment-progress-text">0%</span>
            </div>
            <div>
                <span class="badge bg-info">
                    <span id="alignment-aligned-count">{{ novel.aligned_chapters }}</span> / {{ novel.total_chapters }}
                </span>
            </div>
        </div>
        <div class="progress mt-2" style="height: 20px;">
            <div id="alignment-progress-bar"
                 class="progress-bar progress-bar-striped progress-bar-animated bg-info"
                 role="progressbar"
                 style="width: {{ novel.alignment_progress_percentage }}%"
                 aria-valuenow="{{ novel.alignment_progress_percentage }}"
                 aria-valuemin="0"
                 aria-valuemax="100">
                {{ novel.alignment_progress_percentage }}%
            </div>
        </div>
    </div>
</div>

<script>
// Polling для обновления прогресса выравнивания
setInterval(function() {
    fetch('/api/novels/{{ novel.id }}/alignment-status')
        .then(response => response.json())
        .then(data => {
            if (data.is_running) {
                document.getElementById('alignment-progress-text').textContent = data.progress + '%';
                document.getElementById('alignment-aligned-count').textContent = data.aligned_count;
                document.getElementById('alignment-progress-bar').style.width = data.progress + '%';
                document.getElementById('alignment-progress-bar').textContent = data.progress + '%';
            } else {
                // Задача завершена, перезагружаем страницу
                location.reload();
            }
        });
}, 5000);  // Обновление каждые 5 секунд
</script>
{% endif %}
```

**API endpoint для статуса** (`views.py`):
```python
@main_bp.route('/api/novels/<int:novel_id>/alignment-status')
def get_alignment_status(novel_id):
    """Получить статус выравнивания новеллы"""
    novel = Novel.query.get_or_404(novel_id)

    if not novel.alignment_task_id:
        return jsonify({
            'is_running': False,
            'progress': novel.alignment_progress_percentage,
            'aligned_count': novel.aligned_chapters
        })

    from celery.result import AsyncResult
    task = AsyncResult(novel.alignment_task_id, app=celery)

    if task.state == 'PROGRESS':
        meta = task.info or {}
        return jsonify({
            'is_running': True,
            'state': task.state,
            'progress': meta.get('progress', 0),
            'aligned_count': meta.get('success_count', novel.aligned_chapters),
            'status': meta.get('status', 'Выравнивание...')
        })
    elif task.state in ['PENDING', 'STARTED']:
        return jsonify({
            'is_running': True,
            'state': task.state,
            'progress': 0,
            'aligned_count': novel.aligned_chapters,
            'status': 'Запуск...'
        })
    else:
        return jsonify({
            'is_running': False,
            'state': task.state,
            'progress': novel.alignment_progress_percentage,
            'aligned_count': novel.aligned_chapters
        })
```

---

## 3. Рекомендации по реализации

### 3.1 Порядок внедрения

1. **База данных** (15 мин):
   - ✅ Добавить `alignment_task_id` и `aligned_chapters` в модель Novel
   - ✅ Создать и применить миграцию
   - ✅ Добавить property `alignment_progress_percentage`

2. **Celery задача** (45 мин):
   - ✅ Создать `align_novel_chapters_task` в `celery_tasks.py`
   - ✅ Реализовать параллельную обработку через ThreadPoolExecutor
   - ✅ Добавить thread-safe обновление счётчиков
   - ✅ Реализовать защиту от дублирования

3. **API Endpoints** (30 мин):
   - ✅ Создать `/novels/<id>/start-alignment` (POST)
   - ✅ Создать `/novels/<id>/cancel-alignment` (POST)
   - ✅ Создать `/api/novels/<id>/alignment-status` (GET)

4. **UI** (30 мин):
   - ✅ Добавить кнопку выравнивания в `novel_detail.html`
   - ✅ Добавить JavaScript функцию `cancelAlignment()`
   - ✅ Добавить секцию отображения прогресса
   - ✅ Добавить polling для обновления прогресса

5. **Тестирование** (30 мин):
   - ✅ Тестирование запуска выравнивания
   - ✅ Тестирование параллельной обработки
   - ✅ Тестирование отмены задачи
   - ✅ Тестирование защиты от дублирования

**Общее время**: ~2.5 часа

### 3.2 Отличия от редактирования

| Аспект | Редактирование | Выравнивание |
|--------|----------------|--------------|
| **Входные данные** | `status='translated'` | `original_text` + перевод |
| **Выходные данные** | `chapter.edited_text` | `BilingualAlignment` запись |
| **Статус главы** | Меняется на `'edited'` | НЕ меняется |
| **Сервис** | `OriginalAwareEditorService` | `BilingualAlignmentService` |
| **Защита от дублирования** | Проверка `chapter.status == 'edited'` | Проверка `BilingualAlignment.query.filter_by(chapter_id)` |
| **Цвет кнопки** | `btn-outline-warning` (желтый) | `btn-outline-info` (голубой) |
| **Иконка** | `bi-pencil-square` | `bi-diagram-3` |

### 3.3 Конфигурация потоков

**Добавить в edit_novel.html** (настройки параллелизма):
```html
<div class="mb-3">
    <label for="alignment_threads" class="form-label">Потоки выравнивания</label>
    <input type="number" class="form-control" id="alignment_threads" name="alignment_threads"
           value="{{ novel.config.alignment_threads if novel.config and novel.config.alignment_threads else 3 }}"
           min="1" max="10">
    <div class="form-text">Количество параллельных потоков для выравнивания (1-10, рекомендуется 2-5)</div>
</div>
```

**Обработка в POST** (`views.py`):
```python
novel.config['alignment_threads'] = int(request.form.get('alignment_threads', 3))
```

---

## 4. Преимущества предложенного дизайна

✅ **Консистентность**: Использует те же паттерны что и редактирование
✅ **Масштабируемость**: Параллельная обработка через ThreadPoolExecutor
✅ **Надёжность**: Защита от дублирования, идемпотентность, graceful отмена
✅ **UX**: Real-time прогресс, кнопки отмены, информативные сообщения
✅ **Производительность**: Кэширование результатов в БД
✅ **Логирование**: Подробные логи с префиксом `[Novel:ID, Ch:NUM]`
✅ **Thread-safety**: Lock для безопасного обновления счётчиков
✅ **Гибкость**: Настраиваемое количество потоков из конфига новеллы

---

## 5. Альтернативные подходы (не рекомендуется)

### ❌ Подход 1: Создание выравнивания "на лету" при генерации EPUB
**Проблема**: Медленная генерация EPUB (LLM запросы в синхронном режиме)

### ❌ Подход 2: Выравнивание по одной главе через UI
**Проблема**: Неудобно для больших новелл (сотни глав), нет автоматизации

### ❌ Подход 3: Выравнивание в рамках задачи редактирования
**Проблема**: Смешивание ответственности, сложность отладки

---

## 6. Заключение

**Рекомендуемый дизайн**: Вариант 2 (кнопка во второй строке)

**Архитектура**: Полная аналогия с процессом редактирования
- Модель Novel: `alignment_task_id` + `aligned_chapters`
- Celery задача: `align_novel_chapters_task` с параллельными потоками
- API: `start_alignment`, `cancel_alignment`, `alignment-status`
- UI: Кнопка с переключением запуск/отмена, real-time прогресс

**Ключевые особенности**:
1. Не "кэш", а **постоянные данные** (как редактура)
2. Процесс запускается **вручную кнопкой** (не автоматически)
3. Выравнивание **для каждой главы** создаётся один раз
4. Результаты сохраняются в `bilingual_alignments` таблице
5. Можно **пересоздать** при необходимости (force_refresh)

Этот подход обеспечивает консистентность с существующей архитектурой и предоставляет пользователю полный контроль над процессом выравнивания.
