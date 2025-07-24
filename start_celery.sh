#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
print_message() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка наличия Redis
if ! command -v redis-server &> /dev/null; then
    print_error "Redis не найден. Установите Redis: sudo apt-get install redis-server"
    exit 1
fi

# Проверка статуса Redis
if ! redis-cli ping &> /dev/null; then
    print_warning "Redis не запущен. Запускаю Redis..."
    redis-server --daemonize yes
    sleep 2
fi

# Активация виртуального окружения
print_message "Активация виртуального окружения..."
source .venv/bin/activate

if [ $? -ne 0 ]; then
    print_error "Не удалось активировать виртуальное окружение"
    exit 1
fi

# Проверка переменных окружения
if [ ! -f ".env" ]; then
    print_error "Файл .env не найден. Запустите сначала start_web.sh"
    exit 1
fi

# Загрузка переменных окружения
export $(cat .env | grep -v '^#' | xargs)

print_message "Запуск Celery worker..."
print_message "Для остановки нажмите Ctrl+C"

# Запуск с обработкой сигналов
trap 'print_message "Получен сигнал остановки. Завершение работы..."; exit 0' INT TERM

# Запуск Celery worker
cd web_app
celery -A app.celery worker --loglevel=info --concurrency=2

# Обработка ошибок запуска
if [ $? -ne 0 ]; then
    print_error "Ошибка при запуске Celery worker"
    exit 1
fi 