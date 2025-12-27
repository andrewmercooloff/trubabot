# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем ffmpeg и необходимые зависимости
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY . .

# Создаем директорию для загрузок
RUN mkdir -p downloads

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Запускаем бота
CMD ["python", "bot.py"]

