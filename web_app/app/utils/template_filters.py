"""
Jinja2 фильтры для работы с цветами статусов в шаблонах.
"""

from app.utils.status_colors import status_colors


def register_template_filters(app):
    """Регистрация всех фильтров в приложении Flask"""
    
    @app.template_filter('status_color')
    def status_color_filter(status, entity_type='novel', **kwargs):
        """
        Фильтр для получения цвета статуса
        
        Использование в шаблонах:
        {{ novel.status|status_color('novel') }}
        {{ chapter.status|status_color('chapter') }}
        {{ task.status|status_color('task_status') }}
        {{ task.task_type|status_color('task_type') }}
        """
        return status_colors.get_status_color(status, entity_type, **kwargs)
    
    @app.template_filter('novel_status_color')
    def novel_status_color_filter(status):
        """Фильтр для цвета статуса новеллы"""
        return status_colors.get_novel_status_color(status)
    
    @app.template_filter('chapter_status_color')
    def chapter_status_color_filter(status):
        """Фильтр для цвета статуса главы"""
        return status_colors.get_chapter_status_color(status)
    
    @app.template_filter('task_status_color')
    def task_status_color_filter(status):
        """Фильтр для цвета статуса задачи"""
        return status_colors.get_task_status_color(status)
    
    @app.template_filter('task_type_color')
    def task_type_color_filter(task_type):
        """Фильтр для цвета типа задачи"""
        return status_colors.get_task_type_color(task_type)
    
    @app.template_filter('log_level_color')
    def log_level_color_filter(level):
        """Фильтр для цвета уровня лога"""
        return status_colors.get_log_level_color(level)
    
    @app.template_filter('prompt_template_status_color')
    def prompt_template_status_color_filter(template):
        """Фильтр для цвета статуса шаблона промпта"""
        return status_colors.get_prompt_template_status_color(
            template.is_default, 
            template.is_active
        )
    
    @app.template_filter('status_badge_class')
    def status_badge_class_filter(status, entity_type='novel', **kwargs):
        """
        Фильтр для получения полного класса badge с цветом
        
        Использование:
        {{ novel.status|status_badge_class('novel') }}
        """
        color = status_colors.get_status_color(status, entity_type, **kwargs)
        return f"badge bg-{color}"
    
    @app.template_filter('status_icon')
    def status_icon_filter(status, entity_type='novel'):
        """
        Фильтр для получения иконки статуса
        
        Возвращает класс иконки Bootstrap Icons
        """
        icon_map = {
            'novel': {
                'pending': 'bi-clock',
                'parsing': 'bi-download',
                'translating': 'bi-translate',
                'editing': 'bi-pencil-square',
                'completed': 'bi-check-circle',
                'deleted': 'bi-trash',
            },
            'chapter': {
                'pending': 'bi-clock',
                'parsed': 'bi-file-text',
                'translated': 'bi-translate',
                'edited': 'bi-pencil-square',
                'error': 'bi-exclamation-triangle',
            },
            'task_status': {
                'pending': 'bi-clock',
                'running': 'bi-play-circle',
                'completed': 'bi-check-circle',
                'failed': 'bi-exclamation-triangle',
            },
            'task_type': {
                'parse': 'bi-download',
                'translate': 'bi-translate',
                'edit': 'bi-pencil-square',
                'generate_epub': 'bi-file-earmark-text',
            }
        }
        
        entity_icons = icon_map.get(entity_type, {})
        return entity_icons.get(status, 'bi-question-circle')
    
    @app.template_filter('status_text')
    def status_text_filter(status, entity_type='novel'):
        """
        Фильтр для получения человекочитаемого текста статуса
        """
        text_map = {
            'novel': {
                'pending': 'Ожидание',
                'parsing': 'Парсинг',
                'translating': 'Перевод',
                'editing': 'Редактура',
                'completed': 'Завершено',
                'deleted': 'Удалено',
            },
            'chapter': {
                'pending': 'Ожидание',
                'parsed': 'Распарсено',
                'translated': 'Переведено',
                'edited': 'Отредактировано',
                'error': 'Ошибка',
            },
            'task_status': {
                'pending': 'Ожидание',
                'running': 'Выполняется',
                'completed': 'Завершено',
                'failed': 'Ошибка',
            },
            'task_type': {
                'parse': 'Парсинг',
                'translate': 'Перевод',
                'edit': 'Редактура',
                'generate_epub': 'Генерация EPUB',
            }
        }
        
        entity_texts = text_map.get(entity_type, {})
        return entity_texts.get(status, status) 