# --- Базовый образ ---
FROM python:3.11-slim

# --- Настройки окружения ---
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# --- Установка зависимостей ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Копирование исходного кода ---
COPY . .

# --- Точка запуска ---
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]