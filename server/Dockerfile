# Используем официальный Python-образ
FROM python:3.10-slim

# Создадим рабочую директорию
WORKDIR /app

# Скопируем файлы зависимостей
COPY requirements.txt .

# Установим зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Скопируем исходники
COPY . .

ENV PYTHONPATH=/app

# Запустим сервер
CMD ["python", "main.py"]

