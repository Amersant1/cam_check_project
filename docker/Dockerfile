# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем системные зависимости для аудио и видео
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    alsa-utils \
    pulseaudio \
    ffmpeg \
    libopencv-dev \
    python3-opencv \
    v4l-utils \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgtk-3-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Открываем порт для приложения (если понадобится веб-интерфейс)
EXPOSE 8000

# Команда запуска API сервера
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
