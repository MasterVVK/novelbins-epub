from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from app.models import Novel, Chapter, Task, SystemSettings, PromptTemplate
from app import db, socketio
from app.services.translator_service import TranslatorService
from app.services.parser_service import WebParserService
import threading

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def dashboard():
    """Главная страница - дашборд"""
    novels = Novel.query.filter_by(is_active=True).all()

    # Статистика
    total_novels = len(novels)
    total_chapters = sum(n.total_chapters for n in novels)
    translated_chapters = sum(n.translated_chapters for n in novels)
    edited_chapters = sum(n.edited_chapters for n in novels)

    # Активные задачи
    active_tasks = Task.query.filter_by(status='running').order_by(Task.priority, Task.created_at).limit(10).all()

    return render_template('dashboard.html',
                         novels=novels,
                         total_novels=total_novels,
                         total_chapters=total_chapters,
                         translated_chapters=translated_chapters,
                         edited_chapters=edited_chapters,
                         active_tasks=active_tasks)


@main_bp.route('/novels')
def novels():
    """Список новелл"""
    novels = Novel.query.filter_by(is_active=True).order_by(Novel.created_at.desc()).all()
    return render_template('novels.html', novels=novels)


@main_bp.route('/novels/deleted')
def deleted_novels():
    """Список удаленных новелл"""
    novels = Novel.query.filter_by(is_active=False).order_by(Novel.updated_at.desc()).all()
    return render_template('deleted_novels.html', novels=novels)


@main_bp.route('/novels/new', methods=['GET', 'POST'])
def new_novel():
    """Добавление новой новеллы"""
    if request.method == 'POST':
        title = request.form.get('title')
        source_url = request.form.get('source_url')
        source_type = request.form.get('source_type', 'novelbins')

        if not title or not source_url:
            flash('Заполните все обязательные поля', 'error')
            return redirect(url_for('main.new_novel'))

        novel = Novel(
            title=title,
            source_url=source_url,
            source_type=source_type,
            config={
                'max_chapters': int(request.form.get('max_chapters', 10)),
                'request_delay': float(request.form.get('request_delay', 1.0)),
                'translation_model': request.form.get('translation_model', 'gemini-2.5-flash-preview-05-20'),
                'temperature': float(request.form.get('temperature', 0.1))
            }
        )

        db.session.add(novel)
        db.session.commit()

        flash(f'Новелла "{title}" добавлена', 'success')
        return redirect(url_for('main.novel_detail', novel_id=novel.id))

    return render_template('new_novel.html')


@main_bp.route('/novels/<int:novel_id>/edit', methods=['GET', 'POST'])
def edit_novel(novel_id):
    """Редактирование новеллы"""
    # Принудительно получаем свежие данные из базы без кеширования
    db.session.expire_all()
    
    # Используем обычный SQLAlchemy запрос
    novel = Novel.query.get_or_404(novel_id)
    
    prompt_templates = PromptTemplate.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        title = request.form.get('title')
        original_title = request.form.get('original_title')
        author = request.form.get('author')
        source_url = request.form.get('source_url')
        source_type = request.form.get('source_type', 'novelbins')
        prompt_template_id = request.form.get('prompt_template_id')
        
        if not title or not source_url:
            flash('Заполните все обязательные поля', 'error')
            return redirect(url_for('main.edit_novel', novel_id=novel_id))

        # Обновляем основные поля
        novel.title = title
        novel.original_title = original_title if original_title else None
        novel.author = author if author else None
        novel.source_url = source_url
        novel.source_type = source_type
        
        # Обновляем шаблон промпта
        if prompt_template_id:
            novel.prompt_template_id = int(prompt_template_id) if prompt_template_id != 'none' else None
        else:
            novel.prompt_template_id = None

        # Обновляем конфигурацию
        if not novel.config:
            novel.config = {}
        
        # Получаем данные формы
        max_chapters = request.form.get('max_chapters')
        request_delay = request.form.get('request_delay')
        translation_model = request.form.get('translation_model')
        temperature = request.form.get('temperature')
        
        # Отладочная информация
        print(f"🔍 Данные формы для '{novel.title}':")
        print(f"   max_chapters: {max_chapters} (тип: {type(max_chapters)})")
        print(f"   request_delay: {request_delay} (тип: {type(request_delay)})")
        print(f"   translation_model: {translation_model}")
        print(f"   temperature: {temperature}")
        print(f"   Старая конфигурация: {novel.config}")
        
        # Обновляем конфигурацию с проверкой значений
        new_config = {
            'max_chapters': int(max_chapters) if max_chapters else 10,
            'request_delay': float(request_delay) if request_delay else 1.0,
            'translation_model': translation_model or 'gemini-2.5-flash-preview-05-20',
            'temperature': float(temperature) if temperature else 0.1
        }
        
        # Принудительно обновляем поле config
        novel.config = new_config
        
        print(f"   Новая конфигурация: {novel.config}")

        # Принудительно обновляем объект в сессии
        db.session.add(novel)
        db.session.commit()
        
        # Проверяем, что изменения сохранились в базе
        db.session.refresh(novel)
        print(f"🔍 После commit - конфигурация: {novel.config}")
        print(f"   max_chapters после commit: {novel.config.get('max_chapters')}")
        
        flash(f'Настройки новеллы "{title}" обновлены', 'success')
        return redirect(url_for('main.novel_detail', novel_id=novel.id))

    # Отладочная информация для GET-запроса
    print(f"🔍 GET запрос для '{novel.title}' - конфигурация: {novel.config}")
    if novel.config:
        print(f"   max_chapters: {novel.config.get('max_chapters')}")
        print(f"   request_delay: {novel.config.get('request_delay')}")
    
    return render_template('edit_novel.html', novel=novel, prompt_templates=prompt_templates)


@main_bp.route('/novels/<int:novel_id>/delete', methods=['POST'])
def delete_novel(novel_id):
    """Удаление новеллы"""
    novel = Novel.query.get_or_404(novel_id)
    
    # Получаем название для сообщения
    novel_title = novel.title
    
    # Используем мягкое удаление (деактивация)
    novel.soft_delete()
    db.session.commit()
    
    flash(f'Новелла "{novel_title}" успешно удалена', 'success')
    return redirect(url_for('main.novels'))


@main_bp.route('/novels/<int:novel_id>/restore', methods=['POST'])
def restore_novel(novel_id):
    """Восстановление новеллы"""
    novel = Novel.query.get_or_404(novel_id)
    
    # Получаем название для сообщения
    novel_title = novel.title
    
    # Восстанавливаем новеллу
    novel.restore()
    db.session.commit()
    
    flash(f'Новелла "{novel_title}" успешно восстановлена', 'success')
    return redirect(url_for('main.novels'))


@main_bp.route('/novels/<int:novel_id>')
def novel_detail(novel_id):
    """Детальная страница новеллы"""
    # Принудительно получаем свежие данные из базы без кеширования
    db.session.expire_all()
    
    # Используем обычный SQLAlchemy запрос, но с принудительным обновлением
    novel = Novel.query.get_or_404(novel_id)
    db.session.refresh(novel)
    
    chapters = Chapter.query.filter_by(novel_id=novel_id, is_active=True).order_by(Chapter.chapter_number).all()

    # Отладочная информация
    print(f"🔍 Страница новеллы '{novel.title}' - конфигурация: {novel.config}")
    if novel.config:
        if isinstance(novel.config, dict):
            print(f"   max_chapters: {novel.config.get('max_chapters')} (тип: {type(novel.config.get('max_chapters'))})")
            print(f"   request_delay: {novel.config.get('request_delay')}")
        else:
            print(f"   config тип: {type(novel.config)}")
            print(f"   config значение: {novel.config}")

    return render_template('novel_detail.html', novel=novel, chapters=chapters)


@main_bp.route('/novels/<int:novel_id>/parse', methods=['POST'])
def start_parsing(novel_id):
    """Запуск парсинга новеллы"""
    print(f"🚀 Запрос на парсинг новеллы {novel_id}")
    
    novel = Novel.query.get_or_404(novel_id)
    print(f"📖 Найдена новелла: {novel.title}")

    # Создаем задачу парсинга
    task = Task(
        novel_id=novel_id,
        task_type='parse',
        priority=1,
        status='running',
        progress=0
    )
    db.session.add(task)
    db.session.commit()
    print(f"✅ Задача создана: {task.id}")

    # Запускаем парсинг в отдельном потоке
    def parse_novel():
        try:
            print(f"🔄 Запуск парсинга для новеллы {novel_id}")
            parser = WebParserService()
            print(f"🔧 Парсер создан, начинаем парсинг...")
            success = parser.parse_novel(novel_id, task_id=task.id)
            print(f"✅ Парсинг завершен: {'успешно' if success else 'с ошибкой'}")
            
            # Обновляем статус задачи (на случай, если парсер не обновил)
            if success:
                task.status = 'completed'
                task.progress = 100
            else:
                task.status = 'failed'
            
            db.session.commit()
            print(f"📊 Статус задачи обновлен: {task.status}")
            
        except Exception as e:
            print(f"❌ Ошибка при парсинге: {e}")
            task.status = 'failed'
            db.session.commit()

    # Запускаем парсинг в фоновом режиме
    import threading
    thread = threading.Thread(target=parse_novel)
    thread.daemon = True
    thread.start()
    
    flash('Парсинг запущен в фоновом режиме. Проверьте статус в разделе "Задачи".', 'info')
    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/novels/<int:novel_id>/translate', methods=['POST'])
def start_translation(novel_id):
    """Запуск перевода новеллы"""
    print(f"🚀 Запрос на перевод новеллы {novel_id}")
    
    novel = Novel.query.get_or_404(novel_id)
    print(f"📖 Найдена новелла: {novel.title}")

    # Проверяем наличие шаблона промпта
    prompt_template = novel.get_prompt_template()
    if not prompt_template:
        flash('Не найден шаблон промпта для перевода. Создайте шаблон в настройках.', 'error')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Получаем главы для перевода
    chapters = Chapter.query.filter_by(
        novel_id=novel_id,
        status='parsed',
        is_active=True
    ).order_by(Chapter.chapter_number).all()

    if not chapters:
        flash('Нет глав для перевода', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Создаем задачу перевода
    task = Task(
        novel_id=novel_id,
        task_type='translate',
        priority=2,
        status='running',
        progress=0
    )
    db.session.add(task)
    db.session.commit()

    # Запускаем перевод в отдельном потоке
    def translate_novel():
        try:
            from app.services.translator_service import TranslatorService
            
            translator = TranslatorService()
            total_chapters = len(chapters)
            
            for i, chapter in enumerate(chapters):
                try:
                    # Обновляем прогресс
                    progress = (i / total_chapters) * 100
                    task.update_progress(progress / 100, f"Перевод главы {chapter.chapter_number}")
                    emit_task_update(task.id, progress, 'running')
                    
                    # Переводим главу
                    success = translator.translate_chapter(chapter)
                    if not success:
                        task.fail(f"Ошибка перевода главы {chapter.chapter_number}")
                        return
                    
                    time.sleep(2)  # Пауза между главами
                    
                except Exception as e:
                    task.fail(f"Ошибка перевода главы {chapter.chapter_number}: {e}")
                    return
            
            # Завершаем задачу
            task.complete({
                'translated_chapters': total_chapters,
                'novel_id': novel_id,
                'template_used': prompt_template.name
            })
            novel.update_stats()
            emit_task_update(task.id, 100, 'completed')
            
        except Exception as e:
            task.fail(f"Ошибка перевода: {e}")
            emit_task_update(task.id, 0, 'failed')
    
    thread = threading.Thread(target=translate_novel)
    thread.start()
    
    flash(f'Запущен перевод новеллы "{novel.title}" с шаблоном "{prompt_template.name}"', 'success')
    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/novels/<int:novel_id>/edit', methods=['POST'])
def start_editing(novel_id):
    """Запуск редактуры новеллы"""
    novel = Novel.query.get_or_404(novel_id)

    # Получаем главы для редактуры
    chapters = Chapter.query.filter_by(
        novel_id=novel_id,
        status='translated',
        is_active=True
    ).order_by(Chapter.chapter_number).all()

    if not chapters:
        flash('Нет глав для редактуры', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    flash(f'Редактура запущена для {len(chapters)} глав (заглушка)', 'success')
    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/novels/<int:novel_id>/epub', methods=['POST'])
def generate_epub(novel_id):
    """Генерация EPUB"""
    novel = Novel.query.get_or_404(novel_id)

    # Создаем задачу генерации EPUB
    task = Task(
        novel_id=novel_id,
        task_type='generate_epub',
        priority=2
    )
    db.session.add(task)
    db.session.commit()

    flash('Генерация EPUB запущена (заглушка)', 'success')
    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/chapters/<int:chapter_id>')
def chapter_detail(chapter_id):
    """Детальная страница главы"""
    chapter = Chapter.query.filter_by(id=chapter_id, is_active=True).first_or_404()
    return render_template('chapter_detail.html', chapter=chapter)


@main_bp.route('/chapters/<int:chapter_id>/edit', methods=['GET', 'POST'])
def edit_chapter(chapter_id):
    """Редактирование главы"""
    chapter = Chapter.query.filter_by(id=chapter_id, is_active=True).first_or_404()

    if request.method == 'POST':
        translated_text = request.form.get('translated_text')
        if translated_text:
            # Создаем новый перевод
            from app.models import Translation
            translation = Translation(
                chapter_id=chapter_id,
                translated_text=translated_text,
                translation_type='manual',
                api_used='manual'
            )
            db.session.add(translation)
            chapter.status = 'edited'
            db.session.commit()

            flash('Глава отредактирована', 'success')
            return redirect(url_for('main.chapter_detail', chapter_id=chapter_id))

    return render_template('edit_chapter.html', chapter=chapter)


@main_bp.route('/chapters/<int:chapter_id>/delete', methods=['POST'])
def delete_chapter(chapter_id):
    """Удаление главы"""
    chapter = Chapter.query.filter_by(id=chapter_id, is_active=True).first_or_404()
    
    # Получаем информацию для сообщения
    novel_id = chapter.novel_id
    chapter_number = chapter.chapter_number
    
    # Используем мягкое удаление (деактивация)
    chapter.soft_delete()
    db.session.commit()
    
    flash(f'Глава {chapter_number} успешно удалена', 'success')
    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/chapters/<int:chapter_id>/restore', methods=['POST'])
def restore_chapter(chapter_id):
    """Восстановление главы"""
    chapter = Chapter.query.filter_by(id=chapter_id, is_active=False).first_or_404()
    
    # Получаем информацию для сообщения
    novel_id = chapter.novel_id
    chapter_number = chapter.chapter_number
    
    # Восстанавливаем главу
    chapter.restore()
    db.session.commit()
    
    flash(f'Глава {chapter_number} успешно восстановлена', 'success')
    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/novels/<int:novel_id>/deleted-chapters')
def deleted_chapters(novel_id):
    """Страница удаленных глав новеллы"""
    novel = Novel.query.get_or_404(novel_id)
    deleted_chapters = Chapter.query.filter_by(novel_id=novel_id, is_active=False).order_by(Chapter.chapter_number).all()
    
    return render_template('deleted_chapters.html', novel=novel, chapters=deleted_chapters)


@main_bp.route('/tasks')
def tasks():
    """Список задач"""
    # Автоматически очищаем зависшие задачи
    cleanup_hanging_tasks()
    
    tasks = Task.query.order_by(Task.created_at.desc()).limit(50).all()
    return render_template('tasks.html', tasks=tasks)


def cleanup_hanging_tasks():
    """Автоматическая очистка зависших задач"""
    try:
        from datetime import datetime, timedelta
        
        # Находим зависшие задачи (running более 1 часа)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        hanging_tasks = Task.query.filter(
            Task.status == 'running',
            Task.created_at < cutoff_time
        ).all()
        
        if hanging_tasks:
            for task in hanging_tasks:
                task.status = 'failed'
                task.error_message = 'Задача зависла и была автоматически завершена'
            
            db.session.commit()
            print(f"Автоматически очищено {len(hanging_tasks)} зависших задач")
            
    except Exception as e:
        print(f"Ошибка при автоматической очистке задач: {e}")
        db.session.rollback()


@main_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    """Удаление задачи"""
    task = Task.query.get_or_404(task_id)
    
    try:
        db.session.delete(task)
        db.session.commit()
        flash(f'Задача {task_id} удалена', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении задачи: {e}', 'error')
    
    return redirect(url_for('main.tasks'))


@main_bp.route('/tasks/clear-completed', methods=['POST'])
def clear_completed_tasks():
    """Очистка завершенных задач"""
    try:
        # Удаляем завершенные задачи старше 1 дня
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=1)
        
        completed_tasks = Task.query.filter(
            Task.status.in_(['completed', 'failed']),
            Task.created_at < cutoff_date
        ).all()
        
        deleted_count = 0
        for task in completed_tasks:
            db.session.delete(task)
            deleted_count += 1
        
        db.session.commit()
        flash(f'Удалено {deleted_count} завершенных задач', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при очистке задач: {e}', 'error')
    
    return redirect(url_for('main.tasks'))


@main_bp.route('/tasks/clear-all', methods=['POST'])
def clear_all_tasks():
    """Очистка всех задач"""
    try:
        all_tasks = Task.query.all()
        deleted_count = 0
        
        for task in all_tasks:
            db.session.delete(task)
            deleted_count += 1
        
        db.session.commit()
        flash(f'Удалено {deleted_count} задач', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при очистке задач: {e}', 'error')
    
    return redirect(url_for('main.tasks'))


@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Настройки системы"""
    if request.method == 'POST':
        # Обновление настроек
        settings_data = {
            'default_translation_model': request.form.get('default_translation_model'),
            'default_temperature': float(request.form.get('default_temperature', 0.1)),
            'max_tokens': int(request.form.get('max_tokens', 24000)),
            'max_chapters': int(request.form.get('max_chapters', 10)),
            'request_delay': float(request.form.get('request_delay', 1.0))
        }
        
        # Сохраняем настройки
        for key, value in settings_data.items():
            setting = SystemSettings.query.filter_by(key=key).first()
            if setting:
                setting.value = str(value)
            else:
                setting = SystemSettings(key=key, value=str(value))
                db.session.add(setting)
        
        db.session.commit()
        flash('Настройки обновлены', 'success')
        return redirect(url_for('main.settings'))
    
    # Получаем текущие настройки
    settings_dict = {}
    for setting in SystemSettings.query.all():
        try:
            if setting.key in ['default_temperature', 'request_delay']:
                settings_dict[setting.key] = float(setting.value)
            elif setting.key in ['max_tokens', 'max_chapters']:
                settings_dict[setting.key] = int(setting.value)
            else:
                settings_dict[setting.key] = setting.value
        except:
            settings_dict[setting.key] = setting.value
    
    return render_template('settings.html', settings=settings_dict)


@main_bp.route('/prompt-templates')
def prompt_templates():
    """Страница управления шаблонами промптов"""
    from app.services.prompt_template_service import PromptTemplateService
    
    templates = PromptTemplateService.get_all_templates()
    categories = PromptTemplateService.get_categories()
    
    return render_template('prompt_templates.html', 
                         templates=templates, 
                         categories=categories)


@main_bp.route('/prompt-templates/new', methods=['GET', 'POST'])
def new_prompt_template():
    """Создание нового шаблона промпта"""
    from app.services.prompt_template_service import PromptTemplateService
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'category': request.form.get('category'),
            'translation_prompt': request.form.get('translation_prompt'),
            'summary_prompt': request.form.get('summary_prompt'),
            'terms_extraction_prompt': request.form.get('terms_extraction_prompt'),
            'temperature': float(request.form.get('temperature', 0.1)),
            'max_tokens': int(request.form.get('max_tokens', 24000))
        }
        
        # Валидация
        validation = PromptTemplateService.validate_template_data(data)
        if not validation['valid']:
            flash('Ошибки валидации: ' + ', '.join(validation['errors']), 'error')
            return render_template('new_prompt_template.html', 
                                 template=data, 
                                 categories=PromptTemplateService.get_categories())
        
        # Создание шаблона
        template = PromptTemplateService.create_template(data)
        flash(f'Шаблон "{template.name}" создан', 'success')
        return redirect(url_for('main.prompt_templates'))
    
    categories = PromptTemplateService.get_categories()
    return render_template('new_prompt_template.html', 
                         template={}, 
                         categories=categories)


@main_bp.route('/prompt-templates/<int:template_id>/edit', methods=['GET', 'POST'])
def edit_prompt_template(template_id):
    """Редактирование шаблона промпта"""
    from app.services.prompt_template_service import PromptTemplateService
    
    template = PromptTemplateService.get_template_by_id(template_id)
    if not template:
        flash('Шаблон не найден', 'error')
        return redirect(url_for('main.prompt_templates'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'category': request.form.get('category'),
            'translation_prompt': request.form.get('translation_prompt'),
            'summary_prompt': request.form.get('summary_prompt'),
            'terms_extraction_prompt': request.form.get('terms_extraction_prompt'),
            'temperature': float(request.form.get('temperature', 0.1)),
            'max_tokens': int(request.form.get('max_tokens', 24000))
        }
        
        # Валидация
        validation = PromptTemplateService.validate_template_data(data)
        if not validation['valid']:
            flash('Ошибки валидации: ' + ', '.join(validation['errors']), 'error')
            return render_template('edit_prompt_template.html', 
                                 template=template, 
                                 categories=PromptTemplateService.get_categories())
        
        # Обновление шаблона
        updated_template = PromptTemplateService.update_template(template_id, data)
        flash(f'Шаблон "{updated_template.name}" обновлен', 'success')
        return redirect(url_for('main.prompt_templates'))
    
    categories = PromptTemplateService.get_categories()
    return render_template('edit_prompt_template.html', 
                         template=template, 
                         categories=categories)


@main_bp.route('/prompt-templates/<int:template_id>/delete', methods=['POST'])
def delete_prompt_template(template_id):
    """Удаление шаблона промпта"""
    from app.services.prompt_template_service import PromptTemplateService
    
    template = PromptTemplateService.get_template_by_id(template_id)
    if not template:
        flash('Шаблон не найден', 'error')
        return redirect(url_for('main.prompt_templates'))
    
    if template.is_default:
        flash('Нельзя удалить шаблон по умолчанию', 'error')
        return redirect(url_for('main.prompt_templates'))
    
    template_name = template.name
    PromptTemplateService.delete_template(template_id)
    
    flash(f'Шаблон "{template_name}" удален', 'success')
    return redirect(url_for('main.prompt_templates'))


@main_bp.route('/novels/<int:novel_id>/glossary')
def novel_glossary(novel_id):
    """Страница глоссария новеллы"""
    from app.services.glossary_service import GlossaryService
    
    novel = Novel.query.get_or_404(novel_id)
    glossary = GlossaryService.get_glossary_for_novel(novel_id)
    stats = GlossaryService.get_term_statistics(novel_id)
    categories = GlossaryService.get_categories()
    
    return render_template('novel_glossary.html', 
                         novel=novel,
                         glossary=glossary,
                         stats=stats,
                         categories=categories)


@main_bp.route('/novels/<int:novel_id>/glossary/add', methods=['GET', 'POST'])
def add_glossary_term(novel_id):
    """Добавление термина в глоссарий"""
    from app.services.glossary_service import GlossaryService
    
    novel = Novel.query.get_or_404(novel_id)
    
    if request.method == 'POST':
        data = {
            'english_term': request.form.get('english_term'),
            'russian_term': request.form.get('russian_term'),
            'category': request.form.get('category'),
            'description': request.form.get('description'),
            'first_appearance_chapter': request.form.get('first_appearance_chapter')
        }
        
        # Валидация
        validation = GlossaryService.validate_term_data(data)
        if not validation['valid']:
            flash('Ошибки валидации: ' + ', '.join(validation['errors']), 'error')
            return render_template('add_glossary_term.html', 
                                 novel=novel,
                                 term=data,
                                 categories=GlossaryService.get_categories())
        
        # Добавление термина
        term = GlossaryService.add_term(
            novel_id=novel_id,
            english_term=data['english_term'],
            russian_term=data['russian_term'],
            category=data['category'],
            description=data.get('description', ''),
            chapter_number=int(data['first_appearance_chapter']) if data['first_appearance_chapter'] else None
        )
        
        flash(f'Термин "{term.english_term}" добавлен в глоссарий', 'success')
        return redirect(url_for('main.novel_glossary', novel_id=novel_id))
    
    categories = GlossaryService.get_categories()
    return render_template('add_glossary_term.html', 
                         novel=novel,
                         term={},
                         categories=categories)


@main_bp.route('/novels/<int:novel_id>/glossary/<int:term_id>/edit', methods=['POST'])
def edit_glossary_term(novel_id, term_id):
    """Редактирование термина в глоссарии"""
    from app.services.glossary_service import GlossaryService
    
    novel = Novel.query.get_or_404(novel_id)
    
    data = {
        'english_term': request.form.get('english_term'),
        'russian_term': request.form.get('russian_term'),
        'category': request.form.get('category'),
        'description': request.form.get('description'),
        'first_appearance_chapter': request.form.get('first_appearance_chapter')
    }
    
    # Валидация
    validation = GlossaryService.validate_term_data(data)
    if not validation['valid']:
        flash('Ошибки валидации: ' + ', '.join(validation['errors']), 'error')
        return redirect(url_for('main.novel_glossary', novel_id=novel_id))
    
    # Обновление термина
    updated_term = GlossaryService.update_term(term_id, data)
    if not updated_term:
        flash('Термин не найден', 'error')
        return redirect(url_for('main.novel_glossary', novel_id=novel_id))
    
    flash(f'Термин "{updated_term.english_term}" обновлен', 'success')
    return redirect(url_for('main.novel_glossary', novel_id=novel_id))


@main_bp.route('/novels/<int:novel_id>/glossary/<int:term_id>/delete', methods=['POST'])
def delete_glossary_term(novel_id, term_id):
    """Удаление термина из глоссария"""
    from app.services.glossary_service import GlossaryService
    
    novel = Novel.query.get_or_404(novel_id)
    
    # Удаление термина
    success = GlossaryService.delete_term(term_id)
    if not success:
        flash('Термин не найден', 'error')
        return redirect(url_for('main.novel_glossary', novel_id=novel_id))
    
    flash('Термин удален из глоссария', 'success')
    return redirect(url_for('main.novel_glossary', novel_id=novel_id))


# WebSocket события
@socketio.on('connect')
def handle_connect():
    """Подключение клиента"""
    print('Client connected')


@socketio.on('disconnect')
def handle_disconnect():
    """Отключение клиента"""
    print('Client disconnected')


def emit_task_update(task_id, progress, status, message=None):
    """Отправка обновления задачи через WebSocket"""
    socketio.emit('task_update', {
        'task_id': task_id,
        'progress': progress,
        'status': status,
        'message': message
    }) 