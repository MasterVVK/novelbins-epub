import os
from datetime import timedelta


class Config:
    """Базовая конфигурация"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///novel_translator.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Настройки подключения для PostgreSQL/SQLite
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Проверка соединения перед использованием
        'pool_recycle': 3600,  # Пересоздавать соединения каждый час
        'pool_size': 10,  # Размер пула соединений
        'max_overflow': 20,  # Дополнительные соединения при необходимости
    }

    # Celery - используем Redis DB 1 для изоляции от других worker'ов
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/1'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/1'

    # Flask-SocketIO
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('SOCKETIO_MESSAGE_QUEUE') or 'redis://localhost:6379/0'

    # Загрузка файлов
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # Логирование
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/app.log')
    LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

    # Настройки перевода
    DEFAULT_TRANSLATION_MODEL = 'gemini-2.5-flash'
#    DEFAULT_TRANSLATION_MODEL = 'gemini-2.5-pro'

    DEFAULT_TRANSLATION_TEMPERATURE = 0.1
    DEFAULT_EDITING_TEMPERATURE = 0.7
    MAX_TOKENS = 256000

    # Настройки парсинга
    DEFAULT_REQUEST_DELAY = 1.0
    DEFAULT_MAX_CHAPTERS = 100

    # Настройки редактуры
    DEFAULT_EDITING_STAGES = ['analysis', 'style', 'dialogue', 'polish']
    DEFAULT_QUALITY_THRESHOLD = 7

    # Прокси для API запросов
    PROXY_URL = os.environ.get('PROXY_URL')

    # API ключи
    GEMINI_API_KEYS = os.environ.get('GEMINI_API_KEYS', '').split(',')
    GEMINI_API_KEYS = [key.strip() for key in GEMINI_API_KEYS if key.strip()]
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


class DevelopmentConfig(Config):
    """Конфигурация для разработки"""
    DEBUG = True
    SQLALCHEMY_ECHO = False
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Конфигурация для продакшена"""
    DEBUG = False
    SQLALCHEMY_ECHO = False
    LOG_LEVEL = 'WARNING'


class TestingConfig(Config):
    """Конфигурация для тестирования"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    LOG_LEVEL = 'DEBUG'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
