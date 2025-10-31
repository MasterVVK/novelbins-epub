#!/bin/bash

# Скрипт остановки Celery worker и VNC сервисов

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  Остановка Celery Worker и VNC${NC}"
echo -e "${GREEN}====================================${NC}"
echo

# Остановка Celery worker
echo -e "${YELLOW}Остановка Celery worker...${NC}"
CELERY_PIDS=$(pgrep -f "celery.*worker.*czbooks" || true)
if [ -n "$CELERY_PIDS" ]; then
    echo "$CELERY_PIDS" | xargs kill -TERM 2>/dev/null || true
    sleep 2
    # Проверяем, завершился ли процесс
    CELERY_PIDS=$(pgrep -f "celery.*worker.*czbooks" || true)
    if [ -n "$CELERY_PIDS" ]; then
        echo -e "${YELLOW}⚠️  Принудительная остановка...${NC}"
        echo "$CELERY_PIDS" | xargs kill -9 2>/dev/null || true
    fi
    echo -e "${GREEN}✅ Celery worker остановлен${NC}"
else
    echo -e "${YELLOW}⚠️  Celery worker не запущен${NC}"
fi
echo

# Остановка websockify
echo -e "${YELLOW}Остановка websockify...${NC}"
WEBSOCKIFY_PIDS=$(pgrep -f "websockify.*6080" || true)
if [ -n "$WEBSOCKIFY_PIDS" ]; then
    echo "$WEBSOCKIFY_PIDS" | xargs kill -TERM 2>/dev/null || true
    sleep 1
    echo -e "${GREEN}✅ websockify остановлен${NC}"
else
    echo -e "${YELLOW}⚠️  websockify не запущен${NC}"
fi
echo

# Остановка x11vnc
echo -e "${YELLOW}Остановка x11vnc...${NC}"
X11VNC_PIDS=$(pgrep -f "x11vnc.*5900" || true)
if [ -n "$X11VNC_PIDS" ]; then
    echo "$X11VNC_PIDS" | xargs kill -TERM 2>/dev/null || true
    sleep 1
    echo -e "${GREEN}✅ x11vnc остановлен${NC}"
else
    echo -e "${YELLOW}⚠️  x11vnc не запущен${NC}"
fi
echo

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  Все сервисы остановлены${NC}"
echo -e "${GREEN}====================================${NC}"
