#!/bin/bash

# Скрипт остановки LLM Worker

# НЕ используем set -e — нужно продолжать остановку даже при ошибках

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  Остановка LLM Worker${NC}"
echo -e "${GREEN}====================================${NC}"
echo

# Остановка LLM worker
echo -e "${YELLOW}Остановка LLM worker...${NC}"
LLM_PIDS=$(pgrep -f "celery.*worker.*llm" || true)
if [ -n "$LLM_PIDS" ]; then
    echo "$LLM_PIDS" | xargs kill -TERM 2>/dev/null || true
    sleep 2
    # Проверяем, завершился ли процесс
    LLM_PIDS=$(pgrep -f "celery.*worker.*llm" || true)
    if [ -n "$LLM_PIDS" ]; then
        echo -e "${YELLOW}⚠️  Принудительная остановка...${NC}"
        echo "$LLM_PIDS" | xargs kill -9 2>/dev/null || true
    fi
    echo -e "${GREEN}✅ LLM worker остановлен${NC}"
else
    echo -e "${YELLOW}⚠️  LLM worker не запущен${NC}"
fi
echo

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  LLM Worker остановлен${NC}"
echo -e "${GREEN}====================================${NC}"
