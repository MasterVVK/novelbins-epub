from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from app.models import Novel, Chapter, Task, PromptTemplate, SystemSettings
from app import db, socketio
from sqlalchemy.orm.attributes import flag_modified
from app.services.translator_service import TranslatorService
from app.services.parser_service import WebParserService
from app.services.original_aware_editor_service import OriginalAwareEditorService
from app.services.log_service import LogService
from app.services.parser_integration import ParserIntegrationService
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)


def get_active_task_for_novel(novel):
    """Проверяет, есть ли активная задача у новеллы.
    Возвращает (task_type, task_id) или (None, None).
    Очищает stale task_id если задача завершена."""
    from celery.result import AsyncResult
    from app import celery

    task_fields = [
        ('парсинг', 'parsing_task_id'),
        ('перевод', 'translation_task_id'),
        ('редактура', 'editing_task_id'),
        ('сопоставление', 'alignment_task_id'),
        ('генерация EPUB', 'epub_generation_task_id'),
    ]
    for task_name, field in task_fields:
        task_id = getattr(novel, field)
        if task_id:
            result = AsyncResult(task_id, app=celery)
            if result.state in ['PENDING', 'STARTED', 'PROGRESS']:
                return task_name, task_id
            else:
                # Stale task_id — задача завершена, очищаем
                setattr(novel, field, None)
                db.session.commit()
    return None, None


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
    # Получаем параметр фильтра по автору
    author_filter = request.args.get('author', '').strip()

    # Базовый запрос
    query = Novel.query.filter_by(is_active=True)

    # Применяем фильтр по автору если указан
    if author_filter:
        query = query.filter(Novel.author == author_filter)

    novels = query.order_by(Novel.created_at.desc()).all()

    # Получаем уникальных авторов для списка фильтра
    authors = db.session.query(Novel.author).filter(
        Novel.is_active == True,
        Novel.author.isnot(None),
        Novel.author != ''
    ).distinct().order_by(Novel.author).all()
    authors = [a[0] for a in authors]

    return render_template('novels.html', novels=novels, authors=authors, author_filter=author_filter)


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
        auto_detect = request.form.get('auto_detect', 'false') == 'true'

        if not title:
            flash('Заполните название новеллы', 'error')
            return redirect(url_for('main.new_novel'))

        # Специальная обработка для EPUB источника
        if source_type == 'epub':
            # Проверяем загруженный файл
            epub_file = request.files.get('epub_file')
            if epub_file and epub_file.filename:
                # Валидация файла
                if not epub_file.filename.lower().endswith('.epub'):
                    flash('Выберите файл с расширением .epub', 'error')
                    return redirect(url_for('main.new_novel'))
                
                # Проверка размера файла (100MB)
                epub_file.seek(0, 2)  # Перемещаемся в конец файла
                file_size = epub_file.tell()
                epub_file.seek(0)  # Возвращаемся в начало
                
                max_size = 100 * 1024 * 1024  # 100MB
                if file_size > max_size:
                    flash(f'Файл слишком большой: {file_size / 1024 / 1024:.1f}MB (максимум 100MB)', 'error')
                    return redirect(url_for('main.new_novel'))
                
                # Сохраняем файл
                import os
                from werkzeug.utils import secure_filename
                
                # Создаем папку для EPUB файлов
                epub_dir = os.path.join(current_app.instance_path, 'epub_files')
                os.makedirs(epub_dir, exist_ok=True)
                
                # Генерируем уникальное имя файла
                filename = secure_filename(epub_file.filename)
                base_name, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(os.path.join(epub_dir, filename)):
                    filename = f"{base_name}_{counter}{ext}"
                    counter += 1
                
                epub_path = os.path.join(epub_dir, filename)
                epub_file.save(epub_path)
                
                # Проверяем, что файл действительно EPUB
                try:
                    import zipfile
                    with zipfile.ZipFile(epub_path, 'r') as epub_zip:
                        if 'META-INF/container.xml' not in epub_zip.namelist():
                            os.remove(epub_path)  # Удаляем некорректный файл
                            flash('Выбранный файл не является корректным EPUB файлом', 'error')
                            return redirect(url_for('main.new_novel'))
                except Exception as e:
                    if os.path.exists(epub_path):
                        os.remove(epub_path)
                    flash(f'Ошибка при проверке EPUB файла: {str(e)}', 'error')
                    return redirect(url_for('main.new_novel'))
                
                # Устанавливаем путь к файлу как source_url
                source_url = epub_path
                flash(f'EPUB файл загружен: {filename}', 'info')
            elif not source_url:
                flash('Для EPUB источника необходимо загрузить файл', 'error')
                return redirect(url_for('main.new_novel'))
        else:
            # Для других источников проверяем URL
            if not source_url:
                flash('Заполните URL источника', 'error')
                return redirect(url_for('main.new_novel'))

        # Автоопределение источника если включено
        if auto_detect and source_url:
            detected_source = ParserIntegrationService.detect_source_from_url(source_url)
            if detected_source:
                source_type = detected_source
                flash(f'Автоматически определен источник: {detected_source}', 'info')
            else:
                flash('Не удалось автоматически определить источник, используется выбранный', 'warning')

        # Проверка соответствия URL и источника
        if source_url and not ParserIntegrationService.validate_url_for_source(source_url, source_type):
            detected = ParserIntegrationService.detect_source_from_url(source_url)
            if detected and detected != source_type:
                if source_type == 'epub':
                    flash(f'Предупреждение: Путь к файлу не похож на EPUB файл. Убедитесь, что указан правильный путь.', 'warning')
                else:
                    flash(f'Внимание: URL больше подходит для источника "{detected}", но выбран "{source_type}"', 'warning')

        # Вычисляем температуру редактирования на основе режима качества
        editing_quality_mode = request.form.get('editing_quality_mode', 'balanced')
        editing_temperature_map = {
            'fast': 0.5,
            'balanced': 0.7,
            'quality': 0.9
        }
        editing_temperature = editing_temperature_map.get(editing_quality_mode, 0.7)
        
        # Обрабатываем опцию "все главы"
        all_chapters = request.form.get('all_chapters', 'false') == 'true'
        
        novel = Novel(
            title=title,
            source_url=source_url,
            source_type=source_type,
            config={
                'max_chapters': int(request.form.get('max_chapters', 100)),
                'start_chapter': int(request.form.get('start_chapter', 1)),
                'all_chapters': all_chapters,
                'request_delay': float(request.form.get('request_delay', 1.0)),
                'translation_model': request.form.get('translation_model', 'gemini-2.5-flash'),
                'translation_temperature': float(request.form.get('translation_temperature', 0.1)),
                'editing_temperature': editing_temperature,
                'editing_quality_mode': editing_quality_mode,
                'filter_text': request.form.get('filter_text', '').strip()
            }
        )

        # Устанавливаем путь к EPUB файлу если это EPUB источник
        if source_type == 'epub':
            novel.set_epub_file(source_url)

        # Обрабатываем SOCKS прокси при создании
        proxy_enabled = request.form.get('proxy_enabled', 'false') == 'true'
        socks_proxy = request.form.get('socks_proxy', '').strip()
        
        if proxy_enabled and socks_proxy:
            novel.set_socks_proxy(socks_proxy)
            print(f"🌐 SOCKS прокси установлен для новой новеллы: {socks_proxy}")

        db.session.add(novel)
        db.session.commit()

        flash(f'Новелла "{title}" добавлена с источником {source_type}', 'success')
        return redirect(url_for('main.novel_detail', novel_id=novel.id))

    # Получаем доступные источники для формы
    available_sources = ParserIntegrationService.get_available_sources_with_info()

    # Получаем доступные AI модели из базы данных
    from app.services.ai_adapter_service import AIAdapterService
    ai_models = AIAdapterService.get_available_models(active_only=True)

    return render_template('new_novel.html', available_sources=available_sources, ai_models=ai_models)


@main_bp.route('/api/preview-epub', methods=['POST'])
def api_preview_epub():
    """API endpoint для предпросмотра EPUB файла"""
    try:
        if 'epub_file' not in request.files:
            return jsonify({'error': 'Файл не загружен'}), 400
        
        epub_file = request.files['epub_file']
        if not epub_file.filename:
            return jsonify({'error': 'Файл не выбран'}), 400
        
        # Проверка расширения
        if not epub_file.filename.lower().endswith('.epub'):
            return jsonify({'error': 'Выберите файл с расширением .epub'}), 400
        
        # Проверка размера
        epub_file.seek(0, 2)
        file_size = epub_file.tell()
        epub_file.seek(0)
        
        max_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_size:
            return jsonify({'error': f'Файл слишком большой: {file_size / 1024 / 1024:.1f}MB'}), 400
        
        # Сохраняем временно для анализа
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as temp_file:
            epub_file.save(temp_file.name)
            temp_path = temp_file.name
        
        try:
            # Анализируем EPUB
            from parsers.sources.epub_parser import EPUBParser
            
            parser = EPUBParser(epub_path=temp_path)
            if not parser.chapters:
                return jsonify({'error': 'Не удалось извлечь главы из EPUB файла'}), 400
            
            book_info = parser.get_book_info()
            
            # Получаем информацию о первых главах
            preview_chapters = []
            for i, chapter in enumerate(parser.chapters[:5]):  # Первые 5 глав
                preview_chapters.append({
                    'number': chapter['number'],
                    'title': chapter['title'],
                    'word_count': chapter['word_count']
                })
            
            result = {
                'success': True,
                'book_info': {
                    'title': book_info['title'],
                    'author': book_info['author'],
                    'total_chapters': book_info['total_chapters'],
                    'language': book_info['language']
                },
                'preview_chapters': preview_chapters,
                'file_size_mb': round(file_size / 1024 / 1024, 1)
            }
            
            return jsonify(result)
            
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except Exception as e:
        return jsonify({'error': f'Ошибка при анализе EPUB: {str(e)}'}), 500


@main_bp.route('/api/detect-source', methods=['POST'])
def api_detect_source():
    """API endpoint для автоопределения источника по URL"""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL не указан'}), 400
        
        detected = ParserIntegrationService.detect_source_from_url(url)
        
        if detected:
            source_info = ParserIntegrationService.get_parser_info(detected)
            return jsonify({
                'detected': True,
                'source': detected,
                'info': source_info
            })
        else:
            return jsonify({
                'detected': False,
                'message': 'Источник не распознан'
            })
            
    except Exception as e:
        logger.error(f"Ошибка автоопределения источника: {e}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


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
        
        # Для EPUB источников обновляем также epub_file_path
        if source_type == 'epub':
            novel.epub_file_path = source_url
        
        # Проверяем соответствие URL/пути и типа источника
        if source_url and not ParserIntegrationService.validate_url_for_source(source_url, source_type):
            detected = ParserIntegrationService.detect_source_from_url(source_url)
            if detected and detected != source_type:
                if source_type == 'epub':
                    flash(f'Предупреждение: Путь к файлу не похож на EPUB файл. Убедитесь, что указан правильный путь.', 'warning')
                else:
                    flash(f'Внимание: URL больше подходит для источника "{detected}", но выбран "{source_type}"', 'warning')
        
        # Обновляем шаблон промпта
        if prompt_template_id:
            novel.prompt_template_id = int(prompt_template_id) if prompt_template_id != 'none' else None
        else:
            novel.prompt_template_id = None

        # Обновляем двуязычный шаблон
        bilingual_template_id = request.form.get('bilingual_template_id')
        if bilingual_template_id:
            novel.bilingual_template_id = int(bilingual_template_id) if bilingual_template_id != 'none' else None
        else:
            novel.bilingual_template_id = None

        # Обновляем конфигурацию
        if not novel.config:
            novel.config = {}
        
        # Получаем данные формы
        max_chapters = request.form.get('max_chapters')
        start_chapter = request.form.get('start_chapter')
        request_delay = request.form.get('request_delay')
        translation_model = request.form.get('translation_model')
        translation_temperature = request.form.get('translation_temperature')
        editing_quality_mode = request.form.get('editing_quality_mode', 'balanced')
        editing_threads = request.form.get('editing_threads')
        alignment_threads = request.form.get('alignment_threads')

        # Определяем температуру редактирования
        if editing_quality_mode == 'custom':
            # Берем значение из ручного поля
            editing_temperature_str = request.form.get('editing_temperature')
            try:
                editing_temperature = float(editing_temperature_str) if editing_temperature_str else 0.7
                # Валидация диапазона
                editing_temperature = max(0.0, min(1.0, editing_temperature))
                print(f"🎯 Ручная настройка температуры: {editing_temperature}")
            except (ValueError, TypeError):
                editing_temperature = 0.7
                flash('Некорректное значение температуры, установлено 0.7', 'warning')
                print(f"⚠️  Ошибка парсинга температуры, установлено значение по умолчанию: 0.7")
        else:
            # Вычисляем на основе режима качества
            editing_temperature_map = {
                'fast': 0.5,
                'balanced': 0.7,
                'quality': 0.9
            }
            editing_temperature = editing_temperature_map.get(editing_quality_mode, 0.7)
            print(f"⚙️  Режим '{editing_quality_mode}': температура {editing_temperature}")
        
        # Отладочная информация
        print(f"🔍 Данные формы для '{novel.title}':")
        print(f"   max_chapters: {max_chapters} (тип: {type(max_chapters)})")
        print(f"   request_delay: {request_delay} (тип: {type(request_delay)})")
        print(f"   translation_model: {translation_model}")
        print(f"   translation_temperature: {translation_temperature}")
        print(f"   editing_quality_mode: {editing_quality_mode}")
        print(f"   editing_temperature: {editing_temperature} ({'custom' if editing_quality_mode == 'custom' else 'auto'})")
        print(f"   editing_threads: {editing_threads}")
        print(f"   Старая конфигурация: {novel.config}")
        
        # Обрабатываем опцию "все главы"
        all_chapters = request.form.get('all_chapters', 'false') == 'true'
        
        # Обновляем конфигурацию с проверкой значений
        new_config = {
            'max_chapters': int(max_chapters) if max_chapters else 100,
            'start_chapter': int(start_chapter) if start_chapter else 1,
            'all_chapters': all_chapters,
            'request_delay': float(request_delay) if request_delay else 1.0,
            'translation_model': translation_model or 'gemini-2.5-flash',
            'translation_temperature': float(translation_temperature) if translation_temperature else 0.1,
            'editing_temperature': float(editing_temperature) if editing_temperature else 0.7,
            'editing_quality_mode': editing_quality_mode or 'balanced',
            'editing_threads': int(editing_threads) if editing_threads else 3,
            'alignment_threads': int(alignment_threads) if alignment_threads else 3,
            'filter_text': request.form.get('filter_text', '').strip()
        }
        
        # Принудительно обновляем поле config
        novel.config = new_config
        
        # Важно! Уведомляем SQLAlchemy о том, что JSON поле изменилось
        flag_modified(novel, 'config')
        
        print(f"   Новая конфигурация: {novel.config}")

        # Обрабатываем авторизацию
        auth_enabled = request.form.get('auth_enabled', 'false') == 'true'
        auth_cookies = request.form.get('auth_cookies', '').strip()
        
        if auth_enabled and auth_cookies:
            novel.set_auth_cookies(auth_cookies)
            print(f"🔐 Авторизация включена: {len(auth_cookies)} символов cookies")
        else:
            novel.clear_auth()
            print(f"🔐 Авторизация отключена")
        
        # Обрабатываем VIP авторизацию
        vip_cookies_enabled = request.form.get('vip_cookies_enabled', 'false') == 'true'
        vip_cookies = request.form.get('vip_cookies', '').strip()
        
        if vip_cookies_enabled and vip_cookies:
            novel.set_vip_cookies(vip_cookies)
            print(f"💎 VIP авторизация включена: {len(vip_cookies)} символов cookies")
        else:
            novel.vip_cookies = None
            novel.vip_cookies_enabled = False
            print(f"💎 VIP авторизация отключена")

        # Обрабатываем SOCKS прокси
        proxy_enabled = request.form.get('proxy_enabled', 'false') == 'true'
        socks_proxy = request.form.get('socks_proxy', '').strip()
        
        if proxy_enabled and socks_proxy:
            novel.set_socks_proxy(socks_proxy)
            print(f"🌐 SOCKS прокси включен: {socks_proxy}")
        else:
            novel.clear_proxy()
            print(f"🌐 SOCKS прокси отключен")
        
        # Обрабатываем настройки EPUB
        epub_add_chapter_prefix = request.form.get('epub_add_chapter_prefix', 'auto')
        epub_chapter_prefix_text = request.form.get('epub_chapter_prefix_text')

        # Если значение None (не передано), используем 'Глава' по умолчанию
        # Если пустая строка (удалено пользователем), сохраняем пустую строку
        if epub_chapter_prefix_text is None:
            epub_chapter_prefix_text = 'Глава'
        else:
            epub_chapter_prefix_text = epub_chapter_prefix_text.strip()

        novel.epub_add_chapter_prefix = epub_add_chapter_prefix
        novel.epub_chapter_prefix_text = epub_chapter_prefix_text

        print(f"📚 Настройки EPUB: префикс={epub_add_chapter_prefix}, текст='{epub_chapter_prefix_text}'")

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
    
    # Получаем доступные источники для формы
    available_sources = ParserIntegrationService.get_available_sources_with_info()

    # Получаем доступные AI модели из базы данных
    from app.services.ai_adapter_service import AIAdapterService
    ai_models = AIAdapterService.get_available_models(active_only=True)

    # Получаем доступные двуязычные шаблоны
    from app.services.bilingual_prompt_template_service import BilingualPromptTemplateService
    bilingual_templates = BilingualPromptTemplateService.get_all_templates()

    return render_template('edit_novel.html', novel=novel, prompt_templates=prompt_templates, available_sources=available_sources, ai_models=ai_models, bilingual_templates=bilingual_templates)


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


@main_bp.route('/novels/<int:novel_id>/delete-permanently', methods=['POST'])
def delete_permanently(novel_id):
    """Безвозвратное удаление новеллы"""
    novel = Novel.query.get_or_404(novel_id)
    
    # Получаем название для сообщения перед удалением
    novel_title = novel.title
    
    # Безвозвратное удаление
    db.session.delete(novel)
    db.session.commit()
    
    flash(f'Новелла "{novel_title}" была безвозвратно удалена.', 'success')
    return redirect(url_for('main.deleted_novels'))


@main_bp.route('/novels/<int:novel_id>')
def novel_detail(novel_id):
    """Детальная страница новеллы"""
    from sqlalchemy import func

    # Получаем параметры пагинации
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)  # По умолчанию 100 глав на страницу

    # Ограничиваем количество глав на страницу
    if per_page > 200:
        per_page = 200
    elif per_page < 10:
        per_page = 10

    # Принудительно получаем свежие данные из базы без кеширования
    db.session.expire_all()

    # Используем обычный SQLAlchemy запрос, но с принудительным обновлением
    novel = Novel.query.get_or_404(novel_id)
    db.session.refresh(novel)

    # Подсчитываем РЕАЛЬНОЕ количество глав по статусам из БД
    # Это решает проблему рассинхронизации счётчиков
    chapter_counts = db.session.query(
        Chapter.status,
        func.count(Chapter.id)
    ).filter(
        Chapter.novel_id == novel_id
    ).group_by(Chapter.status).all()

    counts_dict = {status: count for status, count in chapter_counts}

    # Обновляем счётчики в объекте novel реальными значениями из БД
    # (parsed включает всё, что прошло этап парсинга: parsed, translated, edited, aligned)
    # total_chapters берём из novel (установлен парсером), а не из кол-ва глав в БД
    real_in_db = sum(counts_dict.values())
    if not novel.total_chapters or novel.total_chapters < real_in_db:
        novel.total_chapters = real_in_db
    novel.parsed_chapters = counts_dict.get('parsed', 0) + counts_dict.get('translated', 0) + counts_dict.get('edited', 0) + counts_dict.get('aligned', 0)
    novel.translated_chapters = counts_dict.get('translated', 0) + counts_dict.get('edited', 0) + counts_dict.get('aligned', 0)
    novel.edited_chapters = counts_dict.get('edited', 0) + counts_dict.get('aligned', 0)
    novel.aligned_chapters = counts_dict.get('aligned', 0)

    # Получаем главы с пагинацией
    chapters_query = Chapter.query.filter_by(novel_id=novel_id).order_by(Chapter.chapter_number)
    chapters_pagination = chapters_query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    chapters = chapters_pagination.items

    # Получаем задачи для новеллы (включая EPUB)
    tasks = Task.query.filter_by(novel_id=novel_id).order_by(Task.updated_at.desc()).all()

    return render_template('novel_detail.html',
                         novel=novel,
                         chapters=chapters,
                         chapters_pagination=chapters_pagination,
                         tasks=tasks,
                         current_page=page,
                         per_page=per_page)


@main_bp.route('/novels/<int:novel_id>/parse', methods=['POST'])
def start_parsing(novel_id):
    """Запуск парсинга новеллы через Celery"""
    print(f"🚀 Запрос на парсинг новеллы {novel_id}")

    novel = Novel.query.get_or_404(novel_id)
    print(f"📖 Найдена новелла: {novel.title}")

    # Per-novel блокировка: только одна задача на новеллу
    active_task, _ = get_active_task_for_novel(novel)
    if active_task:
        flash(f'Невозможно запустить парсинг: уже выполняется {active_task}', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Получаем параметры из конфига новеллы
    start_chapter = None
    max_chapters = None

    if novel.config:
        start_chapter = novel.config.get('start_chapter')
        # Проверяем опцию "все главы"
        if novel.config.get('all_chapters'):
            max_chapters = None  # None = все главы
        else:
            max_chapters = novel.config.get('max_chapters')

    # Запускаем Celery задачу в очереди czbooks_queue
    try:
        from app.celery_tasks import parse_novel_chapters_task

        task = parse_novel_chapters_task.apply_async(
            kwargs={
                'novel_id': novel_id,
                'start_chapter': start_chapter,
                'max_chapters': max_chapters,
                'use_xvfb': True
            },
            queue='czbooks_queue'
        )

        # Сохраняем task_id
        novel.parsing_task_id = task.id
        novel.status = 'parsing'
        db.session.commit()

        print(f"✅ Celery задача создана: {task.id}")
        flash('Парсинг запущен! Браузер парсера автоматически развернут ниже для прохождения Cloudflare.', 'success')

    except Exception as e:
        print(f"❌ Ошибка запуска Celery задачи: {e}")
        flash(f'Ошибка запуска парсинга: {str(e)}. Убедитесь, что Celery worker запущен.', 'error')

    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/novels/<int:novel_id>/translate', methods=['POST'])
def start_translation(novel_id):
    """Запуск перевода новеллы через Celery"""
    logger.info(f"🚀 Запрос на перевод новеллы {novel_id}")
    novel = Novel.query.get_or_404(novel_id)
    logger.info(f"📖 Найдена новелла: {novel.title}")

    # Per-novel блокировка: только одна задача на новеллу
    active_task, _ = get_active_task_for_novel(novel)
    if active_task:
        flash(f'Невозможно запустить перевод: уже выполняется {active_task}', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Проверяем наличие шаблона промпта
    prompt_template = novel.get_prompt_template()
    if not prompt_template:
        flash('Не найден шаблон промпта для перевода. Создайте шаблон в настройках.', 'error')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Получаем главы для перевода
    chapters = Chapter.query.filter(
        Chapter.novel_id == novel_id,
        Chapter.status == 'parsed',
    ).order_by(Chapter.chapter_number).all()

    logger.info(f"🔍 Найдено глав для перевода: {len(chapters)}")
    for ch in chapters:
        logger.info(f"  - Глава {ch.chapter_number}: {ch.original_title} (статус: {ch.status})")

    if not chapters:
        flash('Нет глав для перевода', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Запускаем Celery задачу перевода
    try:
        from app.celery_tasks import translate_novel_chapters_task
        from app import celery

        chapter_ids = [ch.id for ch in chapters]
        task = translate_novel_chapters_task.apply_async(
            kwargs={
                'novel_id': novel_id,
                'chapter_ids': chapter_ids,
            },
            queue='llm_queue'
        )

        # Сохраняем ID задачи в новелле
        novel.translation_task_id = task.id
        db.session.commit()

        logger.info(f"✅ Task ID: {task.id}, State: {task.state}")
        LogService.log_info(
            f"🎯 Перевод запущен через Celery для {len(chapters)} глав",
            novel_id=novel_id
        )
        flash(f'Перевод запущен для {len(chapters)} глав с шаблоном "{prompt_template.name}"', 'success')

    except Exception as e:
        logger.error(f"❌ Ошибка запуска задачи перевода: {e}")
        flash(f'Ошибка запуска перевода: {str(e)}', 'error')

    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/novels/<int:novel_id>/start-editing', methods=['POST'])
def start_editing(novel_id):
    """Запуск редактуры новеллы через Celery"""
    logger.info(f"🚀 Запрос на редактуру новеллы {novel_id}")
    novel = Novel.query.get_or_404(novel_id)
    logger.info(f"📖 Найдена новелла: {novel.title}")

    # Per-novel блокировка: только одна задача на новеллу
    active_task, _ = get_active_task_for_novel(novel)
    if active_task:
        flash(f'Невозможно запустить редактуру: уже выполняется {active_task}', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Получаем главы для редактуры
    chapters = Chapter.query.filter_by(
        novel_id=novel_id,
        status='translated',
    ).order_by(Chapter.chapter_number).all()

    logger.info(f"🔍 Найдено глав для редактуры: {len(chapters)}")
    for ch in chapters:
        logger.info(f"  - Глава {ch.chapter_number}: {ch.original_title} (статус: {ch.status})")

    if not chapters:
        logger.warning("❌ Нет глав для редактуры")
        flash('Нет глав для редактуры', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Получаем настройку количества потоков из конфига новеллы
    parallel_threads = 3  # По умолчанию
    if novel.config:
        parallel_threads = novel.config.get('editing_threads', 3)

    # Запускаем Celery задачу редактуры
    try:
        from app.celery_tasks import edit_novel_chapters_task
        from app import celery

        # Отладка: выводим конфигурацию Celery
        logger.info(f"🔍 Celery broker: {celery.conf.broker_url}")
        logger.info(f"🔍 Celery backend: {celery.conf.result_backend}")

        chapter_ids = [ch.id for ch in chapters]
        task = edit_novel_chapters_task.apply_async(
            kwargs={
                'novel_id': novel_id,
                'chapter_ids': chapter_ids,
                'parallel_threads': parallel_threads
            },
            queue='llm_queue'
        )

        # Сохраняем ID задачи в новелле
        novel.editing_task_id = task.id
        db.session.commit()

        logger.info(f"✅ Task ID: {task.id}, State: {task.state}")
        LogService.log_info(
            f"🎯 Редактура запущена через Celery для {len(chapters)} глав (потоков: {parallel_threads})",
            novel_id=novel_id
        )
        flash(f'Редактура запущена для {len(chapters)} глав (параллельных потоков: {parallel_threads})', 'success')

    except Exception as e:
        logger.error(f"❌ Ошибка запуска задачи редактуры: {e}")
        flash(f'Ошибка запуска редактуры: {str(e)}', 'error')

    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/novels/<int:novel_id>/start-alignment', methods=['POST'])
def start_alignment(novel_id):
    """Запуск сопоставления с оригиналом новеллы через Celery"""
    logger.info(f"🚀 Запрос на сопоставление новеллы {novel_id}")
    novel = Novel.query.get_or_404(novel_id)
    logger.info(f"📖 Найдена новелла: {novel.title}")

    # Per-novel блокировка: только одна задача на новеллу
    active_task, _ = get_active_task_for_novel(novel)
    if active_task:
        flash(f'Невозможно запустить сопоставление: уже выполняется {active_task}', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Получаем главы для сопоставления
    # ВАЖНО: Только отредактированные (status='edited'), но еще НЕ сопоставленные
    chapters = Chapter.query.filter_by(
        novel_id=novel_id,
        status='edited'  # Только отредактированные, еще не сопоставленные
    ).filter(
        Chapter.original_text.isnot(None),  # Есть китайский оригинал
        Chapter.original_text != ''
    ).order_by(Chapter.chapter_number).all()

    logger.info(f"🔍 Найдено глав для сопоставления: {len(chapters)}")
    for ch in chapters[:5]:  # Логируем первые 5
        logger.info(f"  - Глава {ch.chapter_number}: {ch.original_title} (оригинал: {bool(ch.original_text)})")

    if not chapters:
        logger.warning("❌ Нет глав для сопоставления (нужны отредактированные главы с оригиналом)")
        flash('Нет глав для сопоставления. Требуются отредактированные главы (status=edited) с китайским оригиналом.', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Получаем настройку количества потоков из конфига новеллы
    parallel_threads = 3  # По умолчанию
    if novel.config:
        parallel_threads = novel.config.get('alignment_threads', 3)

    # Запускаем Celery задачу сопоставления
    try:
        from app.celery_tasks import align_novel_chapters_task
        from app import celery

        # Отладка: выводим конфигурацию Celery
        logger.info(f"🔍 Celery broker: {celery.conf.broker_url}")
        logger.info(f"🔍 Celery backend: {celery.conf.result_backend}")

        chapter_ids = [ch.id for ch in chapters]
        task = align_novel_chapters_task.apply_async(
            kwargs={
                'novel_id': novel_id,
                'chapter_ids': chapter_ids,
                'parallel_threads': parallel_threads
            },
            queue='llm_queue'
        )

        # Сохраняем ID задачи в новелле
        novel.alignment_task_id = task.id
        db.session.commit()

        logger.info(f"✅ Task ID: {task.id}, State: {task.state}")
        LogService.log_info(
            f"🎯 Сопоставление запущено через Celery для {len(chapters)} глав (потоков: {parallel_threads})",
            novel_id=novel_id
        )
        flash(f'Сопоставление запущено для {len(chapters)} глав (параллельных потоков: {parallel_threads})', 'success')

    except Exception as e:
        logger.error(f"❌ Ошибка запуска задачи сопоставления: {e}")
        flash(f'Ошибка запуска сопоставления: {str(e)}', 'error')

    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/novels/<int:novel_id>/epub', methods=['POST'])
def generate_epub(novel_id):
    """Генерация EPUB"""
    from app.services.epub_service import EPUBService
    
    novel = Novel.query.get_or_404(novel_id)

    # Per-novel блокировка: только одна задача на новеллу
    active_task, _ = get_active_task_for_novel(novel)
    if active_task:
        flash(f'Невозможно создать EPUB: уже выполняется {active_task}', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Создаем задачу генерации EPUB
    task = Task(
        novel_id=novel_id,
        task_type='generate_epub',
        priority=2,
        status='running'
    )
    db.session.add(task)
    db.session.commit()

    try:
        # Выполняем синхронно без фоновых потоков
        epub_service = EPUBService(current_app)
        
        # Получаем главы для EPUB
        chapters = epub_service.get_edited_chapters_from_db(novel_id)
        
        if not chapters:
            task.status = 'failed'
            task.error_message = 'Нет переведенных глав для создания EPUB'
            db.session.commit()
            flash('Ошибка: нет переведенных глав для создания EPUB', 'error')
            return redirect(url_for('main.novel_detail', novel_id=novel_id))

        # Создаем EPUB
        epub_path = epub_service.create_epub(novel_id, chapters)
        
        # Обновляем статус задачи
        task.status = 'completed'
        task.result = epub_path  # Сохраняем путь как строку
        db.session.commit()
        
        logger.info(f"EPUB создан успешно: {epub_path}")
        flash('EPUB файл успешно создан!', 'success')
        
    except Exception as e:
        logger.error(f"Ошибка при создании EPUB: {e}")
        task.status = 'failed'
        task.error_message = str(e)
        db.session.commit()
        flash(f'Ошибка при создании EPUB: {str(e)}', 'error')

    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/novels/<int:novel_id>/epub/download')
def download_epub(novel_id):
    """Скачивание созданного EPUB файла"""
    from flask import send_file
    from pathlib import Path

    # Ищем последнюю завершенную задачу генерации EPUB
    task = Task.query.filter_by(
        novel_id=novel_id,
        task_type='generate_epub',
        status='completed'
    ).order_by(Task.updated_at.desc()).first()

    if not task or not task.result:
        flash('EPUB файл не найден. Сначала создайте EPUB.', 'error')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    epub_path = Path(task.result)  # task.result теперь содержит путь как строку

    if not epub_path.exists():
        flash('EPUB файл не найден на диске.', 'error')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Получаем название новеллы для имени файла
    novel = Novel.query.get(novel_id)
    filename = f"{novel.title.replace(' ', '_')}.epub" if novel else epub_path.name

    return send_file(
        epub_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/epub+zip'
    )


@main_bp.route('/novels/<int:novel_id>/epub-bilingual', methods=['POST'])
def generate_bilingual_epub(novel_id):
    """Генерация двуязычного EPUB с чередованием русского перевода и китайского оригинала"""
    from app.celery_tasks import generate_bilingual_epub_task

    novel = Novel.query.get_or_404(novel_id)

    # Per-novel блокировка: только одна задача на новеллу
    active_task, _ = get_active_task_for_novel(novel)
    if active_task:
        flash(f'Невозможно создать двуязычный EPUB: уже выполняется {active_task}', 'warning')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    try:
        # Запускаем Celery задачу
        task = generate_bilingual_epub_task.apply_async(
            args=[novel_id],
            queue='llm_queue'
        )

        # Сохраняем task_id
        novel.epub_generation_task_id = task.id
        novel.status = 'generating_epub'
        db.session.commit()

        flash('Генерация двуязычного EPUB запущена в фоновом режиме. Это может занять несколько минут.', 'success')
        logger.info(f"Запущена генерация двуязычного EPUB для новеллы {novel_id}, task_id={task.id}")

    except Exception as e:
        logger.error(f"Ошибка при запуске генерации двуязычного EPUB: {e}")
        flash(f'Ошибка при запуске генерации: {str(e)}', 'error')

    return redirect(url_for('main.novel_detail', novel_id=novel_id))


@main_bp.route('/novels/<int:novel_id>/epub-bilingual/download')
def download_bilingual_epub(novel_id):
    """Скачивание созданного двуязычного EPUB файла"""
    from flask import send_file
    from pathlib import Path

    novel = Novel.query.get_or_404(novel_id)

    # Проверяем наличие EPUB файла
    if not novel.epub_path:
        flash('Двуязычный EPUB файл не найден. Сначала создайте двуязычный EPUB.', 'error')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    epub_path = Path(novel.epub_path)

    if not epub_path.exists():
        flash('Двуязычный EPUB файл не найден на диске.', 'error')
        return redirect(url_for('main.novel_detail', novel_id=novel_id))

    # Формируем имя файла для скачивания
    filename = f"{novel.title.replace(' ', '_')}_bilingual.epub"

    return send_file(
        epub_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/epub+zip'
    )


@main_bp.route('/chapters/<int:chapter_id>')
def chapter_detail(chapter_id):
    """Детальная страница главы"""
    chapter = Chapter.query.get_or_404(chapter_id)

    # Находим предыдущую и следующую главы
    previous_chapter = Chapter.query.filter_by(
        novel_id=chapter.novel_id,
        chapter_number=chapter.chapter_number - 1
    ).first()

    next_chapter = Chapter.query.filter_by(
        novel_id=chapter.novel_id,
        chapter_number=chapter.chapter_number + 1
    ).first()

    # Загружаем историю промптов для главы
    prompt_history = []
    prompt_groups = {}
    
    try:
        from app.models import PromptHistory
        prompt_history = PromptHistory.query.filter_by(
            chapter_id=chapter_id
        ).order_by(PromptHistory.created_at.desc()).all()
        
        # Группируем промпты по категориям
        translation_prompts = []
        editing_prompts = []
        
        for prompt in prompt_history:
            if prompt.prompt_type in ['translation', 'summary', 'terms_extraction']:
                translation_prompts.append(prompt)
            elif prompt.prompt_type.startswith('editing_'):
                editing_prompts.append(prompt)
            else:
                # Для неизвестных типов добавляем в перевод
                translation_prompts.append(prompt)
        
        # Создаем структуру для шаблона
        prompt_groups = {
            'translation': translation_prompts,
            'editing': editing_prompts
        }
        

    except Exception as e:
        # Если таблица не существует или другая ошибка, просто показываем главу без истории промптов
        print(f"Предупреждение: Не удалось загрузить историю промптов: {e}")
        prompt_history = []
        prompt_groups = {}
    
    return render_template('chapter_detail.html', 
                         chapter=chapter, 
                         previous_chapter=previous_chapter,
                         next_chapter=next_chapter,
                         prompt_history=prompt_history,
                         prompt_groups=prompt_groups)


@main_bp.route('/api/chapters/<int:chapter_id>/prompt-history')
def api_chapter_prompt_history(chapter_id):
    """API для получения истории промптов главы"""
    chapter = Chapter.query.get_or_404(chapter_id)
    
    history_data = []
    
    try:
        from app.models import PromptHistory
        prompt_history = PromptHistory.query.filter_by(
            chapter_id=chapter_id
        ).order_by(PromptHistory.created_at.desc()).all()
        
        # Преобразуем в JSON
        for prompt in prompt_history:
            history_data.append({
                'id': prompt.id,
                'prompt_type': prompt.prompt_type,
                'system_prompt': prompt.system_prompt,
                'user_prompt': prompt.user_prompt,
                'response': prompt.response,
                'success': prompt.success,
                'error_message': prompt.error_message,
                'api_key_index': prompt.api_key_index,
                'model_used': prompt.model_used,
                'temperature': prompt.temperature,
                'tokens_used': prompt.tokens_used,
                'finish_reason': prompt.finish_reason,
                'execution_time': prompt.execution_time,
                'created_at': prompt.created_at.isoformat() if prompt.created_at else None
            })
    except Exception as e:
        # Если таблица не существует или другая ошибка, возвращаем пустой список
        print(f"Предупреждение: Не удалось загрузить историю промптов: {e}")
        history_data = []
    
    return jsonify({
        'chapter_id': chapter_id,
        'chapter_number': chapter.chapter_number,
        'total_prompts': len(history_data),
        'prompt_history': history_data
    })


@main_bp.route('/chapters/<int:chapter_id>/edit', methods=['GET', 'POST'])
def edit_chapter(chapter_id):
    """Редактирование главы — все текстовые поля"""
    chapter = Chapter.query.get_or_404(chapter_id)

    if request.method == 'POST':
        from app.models import Translation
        changed = False

        # 1. Заголовки и оригинальный текст (прямые поля Chapter)
        original_title = request.form.get('original_title', '').strip()
        if original_title != (chapter.original_title or ''):
            chapter.original_title = original_title or None
            changed = True

        original_text = request.form.get('original_text', '')
        if original_text != (chapter.original_text or ''):
            chapter.original_text = original_text or None
            changed = True

        # 2. Перевод (Translation с type != 'edited')
        translated_text = request.form.get('translated_text', '')
        translated_title = request.form.get('translated_title', '').strip()
        current = chapter.current_translation

        if translated_text or translated_title:
            if current:
                # Обновляем существующий перевод
                if translated_text and translated_text != (current.translated_text or ''):
                    current.translated_text = translated_text
                    changed = True
                if translated_title != (current.translated_title or ''):
                    current.translated_title = translated_title or None
                    changed = True
            elif translated_text:
                # Создаём новый перевод
                new_translation = Translation(
                    chapter_id=chapter_id,
                    translated_text=translated_text,
                    translated_title=translated_title or None,
                    translation_type='manual',
                    api_used='manual'
                )
                db.session.add(new_translation)
                if chapter.status == 'parsed':
                    chapter.status = 'translated'
                changed = True

        # 3. Отредактированный текст (Translation с type='edited')
        edited_text = request.form.get('edited_text', '')
        edited = chapter.edited_translation

        if edited_text:
            if edited:
                if edited_text != (edited.translated_text or ''):
                    edited.translated_text = edited_text
                    changed = True
            else:
                new_edited = Translation(
                    chapter_id=chapter_id,
                    translated_text=edited_text,
                    translated_title=translated_title or None,
                    translation_type='edited',
                    api_used='manual'
                )
                db.session.add(new_edited)
                if chapter.status == 'translated':
                    chapter.status = 'edited'
                changed = True

        if changed:
            db.session.commit()
            flash('Глава сохранена', 'success')
        else:
            flash('Нет изменений', 'info')

        return redirect(url_for('main.chapter_detail', chapter_id=chapter_id))

    return render_template('edit_chapter.html', chapter=chapter)


@main_bp.route('/chapters/<int:chapter_id>/delete', methods=['POST'])
def delete_chapter(chapter_id):
    """Удаление главы"""
    chapter = Chapter.query.get_or_404(chapter_id)
    
    # Получаем информацию для сообщения
    novel_id = chapter.novel_id
    chapter_number = chapter.chapter_number
    
    # Получаем параметры пагинации для возврата
    return_page = request.form.get('return_page', 1, type=int)
    return_per_page = request.form.get('return_per_page', 100, type=int)
    
    # Полное удаление главы (включая промпты)
    db.session.delete(chapter)
    db.session.commit()
    
    flash(f'Глава {chapter_number} и вся связанная история промптов успешно удалены', 'success')
    
    # Возвращаемся на ту же страницу пагинации
    return redirect(url_for('main.novel_detail', 
                          novel_id=novel_id, 
                          page=return_page, 
                          per_page=return_per_page))





@main_bp.route('/tasks')
def tasks():
    """Список задач"""
    # Автоматически очищаем зависшие задачи
    cleanup_hanging_tasks()
    
    # Загружаем задачи с связанными новеллами
    tasks = Task.query.options(db.joinedload(Task.novel)).order_by(Task.created_at.desc()).limit(50).all()
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


@main_bp.route('/logs')
def logs():
    """Страница просмотра логов"""
    return render_template('logs.html')

@main_bp.route('/console-test')
def console_test():
    """Страница консоли"""
    return render_template('console_working.html')


@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Настройки системы"""
    if request.method == 'POST':
        # Валидация max_tokens
        max_tokens = int(request.form.get('max_tokens', 24000))
        if max_tokens < 1000 or max_tokens > 128000:
            flash('Максимальное количество токенов должно быть от 1000 до 128000', 'error')
            return redirect(url_for('main.settings'))
        
        # Вычисляем температуру перевода на основе режима точности
        translation_accuracy_mode = request.form.get('default_translation_accuracy_mode', 'balanced')
        translation_temperature_map = {
            'maximum': 0.1,
            'balanced': 0.3,
            'free': 0.5
        }
        translation_temperature = translation_temperature_map.get(translation_accuracy_mode, 0.3)
        
        # Вычисляем температуру редактирования на основе режима качества
        editing_quality_mode = request.form.get('default_editing_quality_mode', 'balanced')
        editing_temperature_map = {
            'fast': 0.5,
            'balanced': 0.7,
            'quality': 0.9
        }
        editing_temperature = editing_temperature_map.get(editing_quality_mode, 0.7)
        
        # Обновление настроек
        settings_data = {
            'gemini_api_keys': request.form.get('gemini_api_keys', ''),
            'openai_api_key': request.form.get('openai_api_key', ''),
            'default_translation_model': request.form.get('default_translation_model'),
            'default_translation_temperature': translation_temperature,
            'default_translation_accuracy_mode': translation_accuracy_mode,
            'default_editing_temperature': editing_temperature,
            'default_editing_quality_mode': editing_quality_mode,
            'max_tokens': max_tokens,
            'max_chapters': int(request.form.get('max_chapters', 10)),
            'request_delay': float(request.form.get('request_delay', 1.0)),
            'quality_threshold': int(request.form.get('quality_threshold', 7))
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
            if setting.key in ['default_translation_temperature', 'default_editing_temperature', 'request_delay']:
                settings_dict[setting.key] = float(setting.value)
            elif setting.key in ['max_tokens', 'max_chapters', 'quality_threshold']:
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
            'editing_analysis_prompt': request.form.get('editing_analysis_prompt'),
            'editing_style_prompt': request.form.get('editing_style_prompt'),
            'editing_dialogue_prompt': request.form.get('editing_dialogue_prompt'),
            'editing_final_prompt': request.form.get('editing_final_prompt'),
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
            'editing_analysis_prompt': request.form.get('editing_analysis_prompt'),
            'editing_style_prompt': request.form.get('editing_style_prompt'),
            'editing_dialogue_prompt': request.form.get('editing_dialogue_prompt'),
            'editing_final_prompt': request.form.get('editing_final_prompt'),
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


@main_bp.route('/bilingual-templates')
def bilingual_templates():
    """Страница управления двуязычными шаблонами (LLM выравнивание)"""
    # Получаем доступные AI модели из базы данных
    from app.services.ai_adapter_service import AIAdapterService
    ai_models = AIAdapterService.get_available_models(active_only=True)

    return render_template('bilingual_templates_list.html', ai_models=ai_models)


@main_bp.route('/novels/<int:novel_id>/glossary')
def novel_glossary(novel_id):
    """Страница глоссария новеллы"""
    novel = Novel.query.get_or_404(novel_id)
    return render_template('novel_glossary.html', novel=novel)


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


@main_bp.route('/novels/<int:novel_id>/glossary/clear', methods=['POST'])
def clear_glossary(novel_id):
    """Очистка всего глоссария новеллы"""
    from app.services.glossary_service import GlossaryService
    from app.models import Novel
    
    # Проверка существования новеллы
    novel = Novel.query.get_or_404(novel_id)
    
    # Очищаем глоссарий
    deleted_count = GlossaryService.clear_glossary(novel_id)
    
    flash(f'Глоссарий новеллы "{novel.title}" полностью очищен. Удалено {deleted_count} терминов.', 'success')
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


@main_bp.route('/download-extension')
def download_extension():
    """Страница скачивания Browser Extension"""
    return render_template('download_extension.html')


# ==================== AI Models Management ====================

@main_bp.route('/ai-models')
def ai_models():
    """Страница управления AI моделями"""
    from app.services.ai_model_service import AIModelService

    models = AIModelService.get_all_models(active_only=False)
    return render_template('ai_models.html', models=models)


@main_bp.route('/ai-models/new', methods=['GET', 'POST'])
def new_ai_model():
    """Создание новой AI модели"""
    if request.method == 'POST':
        from app.services.ai_model_service import AIModelService

        try:
            data = request.json
            model = AIModelService.create_model(data)
            return jsonify({'success': True, 'model_id': model.id})
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Ошибка создания модели: {e}")
            return jsonify({'success': False, 'message': 'Внутренняя ошибка сервера'}), 500

    return render_template('new_ai_model.html')


@main_bp.route('/ai-models/<int:model_id>/edit', methods=['GET', 'POST'])
def edit_ai_model(model_id):
    """Редактирование AI модели"""
    from app.services.ai_model_service import AIModelService

    model = AIModelService.get_model_by_id(model_id)
    if not model:
        flash('Модель не найдена', 'error')
        return redirect(url_for('main.ai_models'))

    if request.method == 'POST':
        try:
            data = request.json
            updated_model = AIModelService.update_model(model_id, data)
            return jsonify({'success': True, 'model_id': updated_model.id})
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)}), 400
        except Exception as e:
            logger.error(f"Ошибка обновления модели: {e}")
            return jsonify({'success': False, 'message': 'Внутренняя ошибка сервера'}), 500

    return render_template('edit_ai_model.html', model=model)


@main_bp.route('/api/ai-models', methods=['POST'])
def api_create_ai_model():
    """API для создания AI модели"""
    from app.services.ai_model_service import AIModelService

    try:
        data = request.json
        model = AIModelService.create_model(data)
        return jsonify({'success': True, 'model_id': model.id})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Ошибка создания модели: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@main_bp.route('/api/ai-models/<int:model_id>', methods=['DELETE'])
def api_delete_ai_model(model_id):
    """API для удаления AI модели"""
    from app.services.ai_model_service import AIModelService

    try:
        success = AIModelService.delete_model(model_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Модель не найдена'}), 404
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Ошибка удаления модели: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@main_bp.route('/api/ai-models/<int:model_id>', methods=['PUT'])
def api_update_ai_model(model_id):
    """API для обновления AI модели"""
    from app.services.ai_model_service import AIModelService

    try:
        data = request.json
        model = AIModelService.update_model(model_id, data)
        return jsonify({'success': True, 'model_id': model.id})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Ошибка обновления модели: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@main_bp.route('/api/ai-models/<int:model_id>/test', methods=['POST'])
def api_test_ai_model(model_id):
    """API для тестирования AI модели"""
    from app.services.ai_model_service import AIModelService
    import asyncio

    try:
        # Запускаем асинхронную функцию в синхронном контексте
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(AIModelService.test_model_connection(model_id))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Ошибка тестирования модели: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/ai-models/<int:model_id>/set-default', methods=['POST'])
def api_set_default_ai_model(model_id):
    """API для установки модели по умолчанию"""
    from app.services.ai_model_service import AIModelService

    try:
        model = AIModelService.set_default_model(model_id)
        return jsonify({'success': True, 'model_id': model.id})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Ошибка установки модели по умолчанию: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@main_bp.route('/api/ai-models/<int:model_id>/duplicate', methods=['POST'])
def api_duplicate_ai_model(model_id):
    """API для дублирования модели"""
    from app.services.ai_model_service import AIModelService

    try:
        data = request.json
        new_model = AIModelService.duplicate_model(model_id, data.get('name'), data.get('model_id'))
        return jsonify({'success': True, 'model_id': new_model.id})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Ошибка дублирования модели: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@main_bp.route('/api/ollama/models', methods=['POST'])
def api_fetch_ollama_models():
    """API для получения списка моделей Ollama"""
    from app.services.ai_model_service import AIModelService
    import asyncio

    try:
        data = request.json
        endpoint = data.get('endpoint', 'http://localhost:11434/api')

        # Запускаем асинхронную функцию
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        models = loop.run_until_complete(AIModelService.fetch_ollama_models(endpoint))
        return jsonify(models)
    except Exception as e:
        logger.error(f"Ошибка получения моделей Ollama: {e}")
        return jsonify([]), 500


@main_bp.route('/api/ollama/model-info', methods=['POST'])
def api_get_ollama_model_info():
    """API для получения детальной информации о модели Ollama"""
    from app.services.ai_model_service import AIModelService
    import asyncio

    try:
        data = request.json
        endpoint = data.get('endpoint', 'http://localhost:11434/api')
        model_name = data.get('model_name')

        if not model_name:
            return jsonify({'error': 'model_name is required'}), 400

        # Запускаем асинхронную функцию
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        model_info = loop.run_until_complete(AIModelService.get_ollama_model_info(endpoint, model_name))

        if model_info:
            return jsonify(model_info)
        else:
            return jsonify({'error': 'Failed to get model info'}), 500

    except Exception as e:
        logger.error(f"Ошибка получения информации о модели Ollama: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/openrouter/models', methods=['POST'])
def api_fetch_openrouter_models():
    """API для получения списка моделей OpenRouter"""
    from app.services.ai_model_service import AIModelService
    import asyncio
    import os

    try:
        data = request.json
        api_key = data.get('api_key')  # Опционально, для персонализированных цен

        # Проверяем, откуда взят ключ
        key_source = None
        if api_key:
            key_source = 'user'  # Ключ предоставлен пользователем
        elif os.getenv('OPENROUTER_API_KEY'):
            key_source = 'env'  # Ключ загружен из .env
            # Функция fetch_openrouter_models сама загрузит ключ из env

        # Запускаем асинхронную функцию
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        models = loop.run_until_complete(AIModelService.fetch_openrouter_models(api_key))

        # Фильтруем и сортируем модели по релевантности
        # Приоритизируем популярные и доступные модели
        priority_models = [
            'openai/gpt-4o-mini',
            'openai/gpt-4o',
            'anthropic/claude-3.5-sonnet',
            'google/gemini-2.5-flash',
            'google/gemini-2.5-pro',
            'meta-llama/llama-3.3-70b-instruct',
            'qwen/qwen-2.5-72b-instruct',
            'deepseek/deepseek-v3',
            'mistralai/mixtral-8x22b-instruct'
        ]

        # Разделяем модели на приоритетные и остальные
        priority_list = []
        other_models = []

        for model in models:
            if model['id'] in priority_models:
                priority_list.append(model)
            else:
                other_models.append(model)

        # Сортируем приоритетные модели по порядку в списке
        priority_list.sort(key=lambda x: priority_models.index(x['id'])
                          if x['id'] in priority_models else 999)

        # Объединяем: сначала приоритетные, потом остальные
        sorted_models = priority_list + other_models

        # Возвращаем модели с метаданными
        result = {
            'models': sorted_models,
            'metadata': {
                'count': len(sorted_models),
                'key_source': key_source,  # 'user', 'env', or None
                'personalized': key_source is not None  # True если используются персональные цены
            }
        }

        return jsonify(result)
    except Exception as e:
        logger.error(f"Ошибка при получении списка моделей OpenRouter: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/celery-monitor')
def celery_monitor():
    """Страница мониторинга Celery"""
    return render_template('celery_monitor.html')
