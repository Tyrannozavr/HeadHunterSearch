#!/bin/bash

# Скрипт для быстрого запуска HH.ru Auto Apply

echo "🚀 Запуск HH.ru Auto Apply..."

# Проверяем, существует ли виртуальное окружение
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
echo "🔧 Активация виртуального окружения..."
source venv/bin/activate

# Устанавливаем зависимости
echo "📥 Установка зависимостей..."
pip install -r requirements.txt

# Запускаем приложение
echo "🌟 Запуск приложения..."
echo "🌐 Веб-интерфейс будет доступен по адресу: http://localhost:8000"
echo "📖 Инструкция: ИНСТРУКЦИЯ.md"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

python main.py 