#!/usr/bin/env python3
"""
Запуск веб-приложения из корня проекта
Улучшенная версия с обработкой ошибок и логированием
"""
import sys
import os
import logging
import signal
import atexit
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Настройка окружения для запуска приложения"""
    try:
        # Получаем абсолютный путь к корню проекта
        project_root = Path(__file__).parent.absolute()
        web_app_path = project_root / 'web_app'
        
        # Проверяем существование папки web_app
        if not web_app_path.exists():
            logger.error(f"Папка web_app не найдена: {web_app_path}")
            return False
        
        # Добавляем папку web_app в путь для импорта
        sys.path.insert(0, str(web_app_path))
        
        # Переходим в папку web_app для корректной работы
        os.chdir(str(web_app_path))
        
        logger.info(f"Рабочая директория: {os.getcwd()}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при настройке окружения: {e}")
        return False

def check_dependencies():
    """Проверка необходимых зависимостей"""
    required_modules = [
        'flask',
        'flask_socketio',
        'flask_sqlalchemy',
        'celery'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        logger.error(f"Отсутствуют необходимые модули: {', '.join(missing_modules)}")
        logger.error("Установите зависимости: pip install -r requirements.txt")
        return False
    
    logger.info("Все зависимости найдены")
    return True

def create_app_instance():
    """Создание экземпляра приложения"""
    try:
        from app import create_app, socketio, db
        
        app = create_app()
        
        # Регистрируем команду для инициализации БД
        @app.cli.command("init-db")
        def init_db():
            """Инициализация базы данных"""
            try:
                db.create_all()
                logger.info("База данных инициализирована!")
            except Exception as e:
                logger.error(f"Ошибка при инициализации БД: {e}")
        
        return app, socketio
        
    except ImportError as e:
        logger.error(f"Ошибка импорта приложения: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Ошибка при создании приложения: {e}")
        return None, None

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info(f"Получен сигнал {signum}. Завершение работы...")
    sys.exit(0)

def cleanup():
    """Функция очистки при завершении"""
    logger.info("Выполняется очистка ресурсов...")

def main():
    """Основная функция запуска"""
    logger.info("Запуск Flask приложения...")
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Регистрируем функцию очистки
    atexit.register(cleanup)
    
    # Настройка окружения
    if not setup_environment():
        logger.error("Не удалось настроить окружение")
        sys.exit(1)
    
    # Проверка зависимостей
    if not check_dependencies():
        logger.error("Проверка зависимостей не пройдена")
        sys.exit(1)
    
    # Создание приложения
    app, socketio = create_app_instance()
    if app is None or socketio is None:
        logger.error("Не удалось создать приложение")
        sys.exit(1)
    
    # Настройки запуска
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    logger.info(f"Запуск приложения на {host}:{port}")
    logger.info(f"Режим отладки: {debug}")
    
    try:
        # Запуск приложения
        socketio.run(
            app, 
            host=host, 
            port=port, 
            debug=debug, 
            allow_unsafe_werkzeug=True,
            use_reloader=False  # Отключаем автоперезагрузку для избежания дублирования
        )
    except KeyboardInterrupt:
        logger.info("Приложение остановлено пользователем")
    except Exception as e:
        logger.error(f"Ошибка при запуске приложения: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 