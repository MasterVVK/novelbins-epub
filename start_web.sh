#!/bin/bash

echo "🚀 ЗАПУСК WEB ИНТЕРФЕЙСА ДЛЯ РАСШИФРОВКИ"
echo "========================================="

# Проверяем HTML интерфейс
if [ -f "/home/user/novelbins-epub/qidian_decrypt_interface.html" ]; then
    echo "✅ HTML интерфейс найден"
    
    # Запуск простого веб-сервера
    echo "🌐 Запуск веб-сервера на порту 8080..."
    cd /home/user/novelbins-epub
    
    # Пробуем Python HTTP сервер
    if command -v python3 &> /dev/null; then
        echo "📡 Запуск через Python HTTP сервер..."
        echo "🔗 Откройте: http://localhost:8080/qidian_decrypt_interface.html"
        echo ""
        echo "📋 В интерфейсе:"
        echo "1. Все данные уже загружены"
        echo "2. Нажмите кнопки для расшифровки" 
        echo "3. Результаты отображаются внизу страницы"
        echo ""
        echo "Для остановки нажмите Ctrl+C"
        python3 -m http.server 8080
    else
        echo "❌ Python3 не найден"
    fi
else
    echo "❌ HTML интерфейс не найден"
    echo "Создаем его..."
    python3 /home/user/novelbins-epub/manual_decrypt_interface.py
    
    if [ -f "/home/user/novelbins-epub/qidian_decrypt_interface.html" ]; then
        echo "✅ HTML интерфейс создан"
        echo "🔗 Откройте: /home/user/novelbins-epub/qidian_decrypt_interface.html"
    fi
fi 