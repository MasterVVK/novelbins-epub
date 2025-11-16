"""
Централизованная система цветов для статусов в web_app.

Этот модуль обеспечивает единообразное использование цветов
для всех статусов в приложении.
"""

from typing import Optional


class StatusColors:
    """Класс для управления цветами статусов"""
    
    # Статусы процесса
    PROCESS_PENDING = 'secondary'      # Серый - ожидание
    PROCESS_RUNNING = 'warning'        # Желтый - выполняется
    PROCESS_COMPLETED = 'success'      # Зеленый - завершено
    PROCESS_FAILED = 'danger'          # Красный - ошибка
    
    # Статусы контента (соответствуют цветам действий)
    CONTENT_PARSED = 'primary'         # Синий - распарсено (как кнопка "Парсинг")
    CONTENT_TRANSLATED = 'success'     # Зеленый - переведено (как кнопка "Перевод")
    CONTENT_EDITED = 'warning'         # Желтый - отредактировано (как кнопка "Редактура")
    CONTENT_ALIGNED = 'info'           # Голубой - выровнено (как кнопка "Билингвальное выравнивание")
    CONTENT_ERROR = 'danger'           # Красный - ошибка
    
    # Типы задач (соответствуют цветам действий)
    TASK_PARSE = 'primary'             # Синий - парсинг (как кнопка "Парсинг")
    TASK_TRANSLATE = 'success'         # Зеленый - перевод (как кнопка "Перевод")
    TASK_EDIT = 'warning'              # Желтый - редактура (как кнопка "Редактура")
    TASK_GENERATE_EPUB = 'info'        # Голубой - генерация EPUB (как кнопка "Создать EPUB")
    
    # Специальные статусы
    SPECIAL_DELETED = 'danger'         # Красный - удалено
    SPECIAL_DEFAULT = 'success'        # Зеленый - по умолчанию
    SPECIAL_ACTIVE = 'success'         # Зеленый - активен
    SPECIAL_INACTIVE = 'secondary'     # Серый - неактивен
    
    # Уровни логов
    LOG_INFO = 'info'                  # Синий - информация
    LOG_WARNING = 'warning'            # Желтый - предупреждение
    LOG_ERROR = 'danger'               # Красный - ошибка

    @classmethod
    def get_novel_status_color(cls, status: str) -> str:
        """Получить цвет для статуса новеллы"""
        color_map = {
            'pending': cls.PROCESS_PENDING,
            'parsing': cls.PROCESS_RUNNING,
            'translating': cls.PROCESS_RUNNING,
            'editing': cls.PROCESS_RUNNING,
            'completed': cls.PROCESS_COMPLETED,
            'deleted': cls.SPECIAL_DELETED,
        }
        return color_map.get(status, cls.PROCESS_PENDING)

    @classmethod
    def get_chapter_status_color(cls, status: str) -> str:
        """Получить цвет для статуса главы"""
        color_map = {
            'pending': cls.PROCESS_PENDING,
            'parsed': cls.CONTENT_PARSED,
            'translated': cls.CONTENT_TRANSLATED,
            'edited': cls.CONTENT_EDITED,
            'aligned': cls.CONTENT_ALIGNED,
            'error': cls.CONTENT_ERROR,
        }
        return color_map.get(status, cls.PROCESS_PENDING)

    @classmethod
    def get_task_status_color(cls, status: str) -> str:
        """Получить цвет для статуса задачи"""
        color_map = {
            'pending': cls.PROCESS_PENDING,
            'running': cls.PROCESS_RUNNING,
            'completed': cls.PROCESS_COMPLETED,
            'failed': cls.PROCESS_FAILED,
        }
        return color_map.get(status, cls.PROCESS_PENDING)

    @classmethod
    def get_task_type_color(cls, task_type: str) -> str:
        """Получить цвет для типа задачи"""
        color_map = {
            'parse': cls.TASK_PARSE,
            'translate': cls.TASK_TRANSLATE,
            'edit': cls.TASK_EDIT,
            'generate_epub': cls.TASK_GENERATE_EPUB,
        }
        return color_map.get(task_type, cls.TASK_PARSE)

    @classmethod
    def get_prompt_template_status_color(cls, is_default: bool, is_active: bool) -> str:
        """Получить цвет для статуса шаблона промпта"""
        if is_default:
            return cls.SPECIAL_DEFAULT
        return cls.SPECIAL_ACTIVE if is_active else cls.SPECIAL_INACTIVE

    @classmethod
    def get_log_level_color(cls, level: str) -> str:
        """Получить цвет для уровня лога"""
        level_upper = level.upper()
        color_map = {
            'INFO': cls.LOG_INFO,
            'WARNING': cls.LOG_WARNING,
            'ERROR': cls.LOG_ERROR,
        }
        return color_map.get(level_upper, cls.LOG_INFO)

    @classmethod
    def get_status_color(cls, status: str, entity_type: str = 'novel', **kwargs) -> str:
        """Универсальный метод для получения цвета статуса"""
        if entity_type == 'novel':
            return cls.get_novel_status_color(status)
        elif entity_type == 'chapter':
            return cls.get_chapter_status_color(status)
        elif entity_type == 'task_status':
            return cls.get_task_status_color(status)
        elif entity_type == 'task_type':
            return cls.get_task_type_color(status)
        elif entity_type == 'prompt_template':
            is_default = kwargs.get('is_default', False)
            is_active = kwargs.get('is_active', True)
            return cls.get_prompt_template_status_color(is_default, is_active)
        elif entity_type == 'log':
            return cls.get_log_level_color(status)
        else:
            return cls.PROCESS_PENDING

    @classmethod
    def get_status_icon(cls, status: str, entity_type: str = 'novel') -> str:
        """Получить иконку для статуса"""
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
                'aligned': 'bi-diagram-3',
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

    @classmethod
    def get_status_text(cls, status: str, entity_type: str = 'novel') -> str:
        """Получить человекочитаемый текст статуса"""
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
                'aligned': 'Сопоставлено',
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

    @classmethod
    def get_all_colors(cls) -> dict:
        """Получить все определенные цвета для документации"""
        return {
            'process': {
                'pending': cls.PROCESS_PENDING,
                'running': cls.PROCESS_RUNNING,
                'completed': cls.PROCESS_COMPLETED,
                'failed': cls.PROCESS_FAILED,
            },
            'content': {
                'parsed': cls.CONTENT_PARSED,
                'translated': cls.CONTENT_TRANSLATED,
                'edited': cls.CONTENT_EDITED,
                'error': cls.CONTENT_ERROR,
            },
            'task_types': {
                'parse': cls.TASK_PARSE,
                'translate': cls.TASK_TRANSLATE,
                'edit': cls.TASK_EDIT,
                'generate_epub': cls.TASK_GENERATE_EPUB,
            },
            'special': {
                'deleted': cls.SPECIAL_DELETED,
                'default': cls.SPECIAL_DEFAULT,
                'active': cls.SPECIAL_ACTIVE,
                'inactive': cls.SPECIAL_INACTIVE,
            },
            'logs': {
                'info': cls.LOG_INFO,
                'warning': cls.LOG_WARNING,
                'error': cls.LOG_ERROR,
            }
        }


# Создаем глобальный экземпляр для удобства использования
status_colors = StatusColors() 