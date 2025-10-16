import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_cors import CORS
from celery import Celery
from config import config

# Инициализация расширений
db = SQLAlchemy()
migrate = Migrate()
socketio = SocketIO()

# Получаем конфигурацию для Celery из config
_config_name = os.environ.get('FLASK_ENV', 'development')
_app_config = config[_config_name]
# Инициализируем Celery с правильным broker/backend сразу
celery = Celery(
    __name__,
    broker=_app_config.CELERY_BROKER_URL,
    backend=_app_config.CELERY_RESULT_BACKEND
)


def setup_logging(app):
    """Настройка логирования"""
    # Создаем папку для логов если её нет
    log_dir = os.path.dirname(app.config['LOG_FILE'])
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настраиваем уровень логирования
    log_level = getattr(logging, app.config['LOG_LEVEL'].upper())
    
    # Форматтер для логов
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    
    # Хендлер для файла
    file_handler = RotatingFileHandler(
        app.config['LOG_FILE'],
        maxBytes=app.config['LOG_MAX_SIZE'],
        backupCount=app.config['LOG_BACKUP_COUNT']
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # Хендлер для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Настраиваем корневой логгер
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
    
    # Логируем запуск приложения
    app.logger.info('Novel Translator startup')


def create_app(config_name=None):
    """Фабрика приложений Flask"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Настройка логирования
    setup_logging(app)

    # Инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins="*")
    CORS(app)

    # Настройка Celery - ВАЖНО: нужно установить до регистрации задач
    celery.conf.broker_url = app.config['CELERY_BROKER_URL']
    celery.conf.result_backend = app.config['CELERY_RESULT_BACKEND']
    # Также обновляем остальную конфигурацию
    celery.conf.update(app.config)
    # Принудительно переподключаемся к новому broker
    celery.set_current()
    celery.set_default()

    # ВАЖНО: Импортируем задачи чтобы Celery их зарегистрировал
    with app.app_context():
        from . import celery_tasks

    # Регистрация blueprints
    from .api import api_bp
    from .api.chapters import chapters_bp
    from .views import main_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(chapters_bp)
    app.register_blueprint(main_bp)

    # Регистрация фильтров для шаблонов
    from .utils.template_filters import register_template_filters
    register_template_filters(app)

    # Создание папок
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    return app


def create_celery(app):
    """Создание Celery приложения"""
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
