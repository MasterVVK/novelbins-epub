#!/bin/bash

# Скрипт запуска Celery worker с Xvfb для парсинга czbooks.net
# Использует виртуальный дисплей для non-headless Chrome

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  Celery Worker для Novel Translator${NC}"
echo -e "${GREEN}====================================${NC}"
echo

# Проверка зависимостей
echo -e "${YELLOW}Проверка зависимостей...${NC}"

if ! command -v xvfb-run &> /dev/null; then
    echo -e "${RED}❌ xvfb-run не найден!${NC}"
    echo "Установите: sudo apt-get install xvfb"
    exit 1
fi

if ! command -v redis-server &> /dev/null; then
    echo -e "${RED}❌ Redis не найден!${NC}"
    echo "Установите: sudo apt-get install redis-server"
    exit 1
fi
echo -e "${GREEN}✅ Все зависимости установлены${NC}"
echo

# Проверка Redis
echo -e "${YELLOW}Проверка Redis...${NC}"
if ! redis-cli ping &> /dev/null; then
    echo -e "${YELLOW}⚠️  Redis не запущен, запускаем...${NC}"
    sudo systemctl start redis-server || sudo service redis-server start
    sleep 2
fi

if redis-cli ping &> /dev/null; then
    echo -e "${GREEN}✅ Redis работает${NC}"
else
    echo -e "${RED}❌ Не удалось запустить Redis${NC}"
    exit 1
fi
echo

# Активация виртуального окружения
if [ -d "../.venv" ]; then
    echo -e "${YELLOW}Активация виртуального окружения...${NC}"
    source ../.venv/bin/activate
    echo -e "${GREEN}✅ Виртуальное окружение активировано${NC}"
else
    echo -e "${RED}❌ Виртуальное окружение не найдено!${NC}"
    echo "Создайте venv в корне проекта: python3 -m venv .venv"
    exit 1
fi
echo

# Установка переменных окружения
export FLASK_APP=app:create_app
export FLASK_ENV=development

# Настройки Celery - используем отдельную Redis базу для изоляции от других worker'ов
export CELERY_BROKER_URL=redis://localhost:6379/1
export CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Настройки Xvfb
XVFB_DISPLAY=":99"
XVFB_RESOLUTION="1920x1080x24"

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  Запуск VNC сервисов${NC}"
echo -e "${GREEN}====================================${NC}"
echo

# Запуск websockify для noVNC (если еще не запущен)
echo -e "${YELLOW}Проверка websockify...${NC}"
if pgrep -f "websockify.*6080" > /dev/null; then
    echo -e "${GREEN}✅ websockify уже запущен${NC}"
else
    echo -e "${YELLOW}🚀 Запуск websockify...${NC}"
    nohup python -m websockify \
        --web ./app/static/novnc \
        6080 \
        localhost:5900 \
        > /tmp/websockify.log 2>&1 &
    sleep 2
    if pgrep -f "websockify.*6080" > /dev/null; then
        echo -e "${GREEN}✅ websockify запущен на порту 6080${NC}"
    else
        echo -e "${RED}⚠️  Не удалось запустить websockify (продолжаем без VNC веб-доступа)${NC}"
    fi
fi
echo

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  Запуск Celery Worker${NC}"
echo -e "${GREEN}====================================${NC}"
echo
echo -e "📊 ${YELLOW}Параметры запуска:${NC}"
echo "  • Виртуальный дисплей: $XVFB_DISPLAY"
echo "  • Разрешение: $XVFB_RESOLUTION"
echo "  • Redis: localhost:6379/1 (dedicated database)"
echo "  • Queue: czbooks_queue (только парсинг)"
echo "  • Concurrency: 1 worker (для czbooks.net)"
echo "  • Pool: solo (для Selenium)"
echo "  • Loglevel: INFO"
echo "  • VNC веб-доступ: http://localhost:6080/vnc.html"
echo
echo -e "${YELLOW}💡 LLM задачи (перевод, редактура, сопоставление, EPUB) запускаются отдельно:${NC}"
echo -e "${YELLOW}   ./start_llm_worker.sh${NC}"
echo

# Запуск Celery worker через Xvfb
echo -e "${GREEN}🚀 Запуск worker...${NC}"
echo

xvfb-run \
    --auto-servernum \
    --server-args="-screen 0 $XVFB_RESOLUTION" \
    celery -A celery_app.celery worker \
        --loglevel=INFO \
        --concurrency=1 \
        --pool=solo \
        --queues=czbooks_queue \
        --hostname=worker-czbooks@%h

# Примечание: используем --pool=solo вместо prefork
# чтобы избежать проблем с Selenium в multiprocessing
