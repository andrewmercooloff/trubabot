# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем ffmpeg и необходимые зависимости
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Сначала копируем requirements.txt для кеширования слоев
COPY requirements.txt .

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальные файлы проекта
COPY . .

# Создаем директорию для загрузок
RUN mkdir -p downloads

# Запускаем бота
CMD ["python", "bot.py"]

