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

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    print_error "Python3 не найден. Установите Python 3.8+"
    exit 1
fi

# Проверка версии Python
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    print_error "Требуется Python 3.8 или выше. Текущая версия: $PYTHON_VERSION"
    exit 1
fi

print_message "Python версия: $PYTHON_VERSION"

# Проверка наличия виртуального окружения
if [ ! -d ".venv" ]; then
    print_warning "Виртуальное окружение не найдено. Создаю новое..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        print_error "Не удалось создать виртуальное окружение"
        exit 1
    fi
    print_success "Виртуальное окружение создано"
fi

# Активация виртуального окружения
print_message "Активация виртуального окружения..."
source .venv/bin/activate

if [ $? -ne 0 ]; then
    print_error "Не удалось активировать виртуальное окружение"
    exit 1
fi

# Проверка и установка зависимостей
if [ ! -f "requirements.txt" ]; then
    print_error "Файл requirements.txt не найден"
    exit 1
fi

print_message "Проверка зависимостей..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    print_error "Не удалось установить зависимости"
    exit 1
fi

print_success "Зависимости установлены"

# Проверка наличия Redis (для Celery)
if ! command -v redis-server &> /dev/null; then
    print_warning "Redis не найден. Celery может работать некорректно."
    print_warning "Установите Redis: sudo apt-get install redis-server"
fi

# Создание необходимых директорий
print_message "Создание необходимых директорий..."
mkdir -p uploads
mkdir -p web_app/uploads
mkdir -p instance

# Проверка переменных окружения
if [ ! -f ".env" ]; then
    print_warning "Файл .env не найден. Создаю базовый .env файл..."
    cat > .env << EOF
# Flask настройки
FLASK_APP=web_app/run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-change-this

# База данных
DATABASE_URL=sqlite:///instance/app.db

# API ключи (заполните своими)
OPENAI_API_KEY=your-openai-api-key
GOOGLE_API_KEY=your-google-api-key

# Redis для Celery
REDIS_URL=redis://localhost:6379/0

# Настройки приложения
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216
EOF
    print_success "Файл .env создан. Отредактируйте его с вашими настройками."
fi

# Запуск веб-приложения
print_message "Запуск Flask приложения..."
print_message "Приложение будет доступно по адресу: http://localhost:5001"
print_message "Для остановки нажмите Ctrl+C"

# Запуск с обработкой сигналов
trap 'print_message "Получен сигнал остановки. Завершение работы..."; exit 0' INT TERM

python3 run_web.py

# Обработка ошибок запуска
if [ $? -ne 0 ]; then
    print_error "Ошибка при запуске приложения"
    exit 1
fi 