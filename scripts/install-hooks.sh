#!/bin/bash
#
# Установка git hooks для проекта
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

echo "📦 Установка git hooks..."

# Проверяем, что мы в git репозитории
if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo "❌ Ошибка: не найден .git директория"
    exit 1
fi

# Создаём директорию hooks если её нет
mkdir -p "$HOOKS_DIR"

# Копируем pre-commit hook
if [ -f "$SCRIPT_DIR/pre-commit" ]; then
    cp "$SCRIPT_DIR/pre-commit" "$HOOKS_DIR/pre-commit"
    chmod +x "$HOOKS_DIR/pre-commit"
    echo "✅ pre-commit hook установлен"
else
    echo "❌ Не найден scripts/pre-commit"
    exit 1
fi

echo ""
echo "🎉 Git hooks успешно установлены!"
echo ""
echo "Проверить работу: git commit --allow-empty -m 'test hook'"
