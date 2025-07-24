import os
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
celery = Celery(__name__)


def create_app(config_name=None):
    """Фабрика приложений Flask"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins="*")
    CORS(app)

    # Настройка Celery
    celery.conf.update(app.config)

    # Регистрация blueprints
    from .api import api_bp
    from .views import main_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(main_bp)

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
