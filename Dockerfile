FROM python:3.10-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создание директории для данных
RUN mkdir -p /app/data

# Копирование кода приложения
COPY . .