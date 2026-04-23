#!/bin/bash

# LLM Worker: перевод, редактура, сопоставление, генерация EPUB
# Без Xvfb — не нужен Selenium
# Запускается ОТДЕЛЬНО от parsing worker'а (start_celery_worker.sh)

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  LLM Worker для Novel Translator${NC}"
echo -e "${GREEN}====================================${NC}"
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

# Настройки Celery — та же Redis база, что и parsing worker
export CELERY_BROKER_URL=redis://localhost:6379/1
export CELERY_RESULT_BACKEND=redis://localhost:6379/1

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  Запуск LLM Worker${NC}"
echo -e "${GREEN}====================================${NC}"
echo
echo -e "📊 ${YELLOW}Параметры запуска:${NC}"
echo "  • Redis: localhost:6379/1"
echo "  • Queue: llm_queue (перевод, редактура, сопоставление, EPUB)"
echo "  • Concurrency: 12 (до 12 новелл параллельно)"
echo "  • Pool: prefork"
echo "  • Loglevel: INFO"
echo
echo -e "${YELLOW}💡 Parsing worker запускается отдельно: ./start_celery_worker.sh${NC}"
echo

# Запуск Celery worker
echo -e "${GREEN}🚀 Запуск LLM worker...${NC}"
echo

celery -A celery_app.celery worker \
    --loglevel=INFO \
    --concurrency=12 \
    --pool=prefork \
    --queues=llm_queue \
    --hostname=worker-llm@%h
