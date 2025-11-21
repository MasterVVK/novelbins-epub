/**
 * JavaScript утилита для работы с цветами статусов
 * Обеспечивает единообразие цветов между серверной и клиентской частью
 */

const StatusColors = {
    // Статусы процесса
    PROCESS_PENDING: 'secondary',      // Серый - ожидание
    PROCESS_RUNNING: 'warning',        // Желтый - выполняется
    PROCESS_COMPLETED: 'success',      // Зеленый - завершено
    PROCESS_FAILED: 'danger',          // Красный - ошибка
    
    // Статусы контента
    CONTENT_PARSED: 'info',            // Синий - распарсено
    CONTENT_TRANSLATED: 'primary',     // Темно-синий - переведено
    CONTENT_EDITED: 'success',         // Зеленый - отредактировано
    CONTENT_ERROR: 'danger',           // Красный - ошибка
    
    // Типы задач
    TASK_PARSE: 'info',                // Синий - парсинг
    TASK_TRANSLATE: 'primary',         // Темно-синий - перевод
    TASK_EDIT: 'warning',              // Желтый - редактура
    TASK_GENERATE_EPUB: 'dark',        // Темно-серый - генерация EPUB
    
    // Специальные статусы
    SPECIAL_DELETED: 'danger',         // Красный - удалено
    SPECIAL_DEFAULT: 'success',        // Зеленый - по умолчанию
    SPECIAL_ACTIVE: 'success',         // Зеленый - активен
    SPECIAL_INACTIVE: 'secondary',     // Серый - неактивен
    
    // Уровни логов
    LOG_INFO: 'info',                  // Синий - информация
    LOG_WARNING: 'warning',            // Желтый - предупреждение
    LOG_ERROR: 'danger',               // Красный - ошибка

    /**
     * Получить цвет для статуса новеллы
     */
    getNovelStatusColor(status) {
        const colorMap = {
            'pending': this.PROCESS_PENDING,
            'parsing': this.PROCESS_RUNNING,
            'translating': this.PROCESS_RUNNING,
            'editing': this.PROCESS_RUNNING,
            'completed': this.PROCESS_COMPLETED,
            'deleted': this.SPECIAL_DELETED,
        };
        return colorMap[status] || this.PROCESS_PENDING;
    },

    /**
     * Получить цвет для статуса главы
     */
    getChapterStatusColor(status) {
        const colorMap = {
            'pending': this.PROCESS_PENDING,
            'parsed': this.CONTENT_PARSED,
            'translated': this.CONTENT_TRANSLATED,
            'edited': this.CONTENT_EDITED,
            'error': this.CONTENT_ERROR,
        };
        return colorMap[status] || this.PROCESS_PENDING;
    },

    /**
     * Получить цвет для статуса задачи
     */
    getTaskStatusColor(status) {
        const colorMap = {
            'pending': this.PROCESS_PENDING,
            'running': this.PROCESS_RUNNING,
            'completed': this.PROCESS_COMPLETED,
            'failed': this.PROCESS_FAILED,
        };
        return colorMap[status] || this.PROCESS_PENDING;
    },

    /**
     * Получить цвет для типа задачи
     */
    getTaskTypeColor(taskType) {
        const colorMap = {
            'parse': this.TASK_PARSE,
            'translate': this.TASK_TRANSLATE,
            'edit': this.TASK_EDIT,
            'generate_epub': this.TASK_GENERATE_EPUB,
        };
        return colorMap[taskType] || this.TASK_PARSE;
    },

    /**
     * Получить цвет для уровня лога
     */
    getLogLevelColor(level) {
        const levelUpper = level.toUpperCase();
        const colorMap = {
            'INFO': this.LOG_INFO,
            'WARNING': this.LOG_WARNING,
            'ERROR': this.LOG_ERROR,
        };
        return colorMap[levelUpper] || this.LOG_INFO;
    },

    /**
     * Получить полный класс badge с цветом
     */
    getBadgeClass(color) {
        return `badge bg-${color}`;
    },

    /**
     * Получить иконку для статуса
     */
    getStatusIcon(status, entityType = 'novel') {
        const iconMap = {
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
        };
        
        const entityIcons = iconMap[entityType] || {};
        return entityIcons[status] || 'bi-question-circle';
    },

    /**
     * Получить человекочитаемый текст статуса
     */
    getStatusText(status, entityType = 'novel') {
        const textMap = {
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
        };
        
        const entityTexts = textMap[entityType] || {};
        return entityTexts[status] || status;
    },

    /**
     * Создать HTML badge для статуса
     */
    createStatusBadge(status, entityType = 'novel') {
        const color = this.getStatusColor(status, entityType);
        const icon = this.getStatusIcon(status, entityType);
        const text = this.getStatusText(status, entityType);
        
        return `<span class="badge bg-${color}">
            <i class="${icon}"></i>
            ${text}
        </span>`;
    },

    /**
     * Универсальный метод для получения цвета статуса
     */
    getStatusColor(status, entityType = 'novel') {
        switch (entityType) {
            case 'novel':
                return this.getNovelStatusColor(status);
            case 'chapter':
                return this.getChapterStatusColor(status);
            case 'task_status':
                return this.getTaskStatusColor(status);
            case 'task_type':
                return this.getTaskTypeColor(status);
            case 'log':
                return this.getLogLevelColor(status);
            default:
                return this.PROCESS_PENDING;
        }
    }
};

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StatusColors;
}

// Экспорт для браузера (делаем глобальной переменной)
if (typeof window !== 'undefined') {
    window.StatusColors = StatusColors;
} 