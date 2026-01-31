# Dockerfile
FROM python:3.11-slim as builder

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libwebp-dev \
    tcl-dev \
    tk-dev \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Установка Python зависимостей
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Сборка статики
RUN python manage.py collectstatic --noinput

# Создание пользователя
RUN useradd -m -u 1000 chronomail && \
    chown -R chronomail:chronomail /app
USER chronomail

# Финальный образ
FROM python:3.11-slim

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y \
    libpq5 \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libwebp-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование зависимостей и статики из builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Создание пользователя
RUN useradd -m -u 1000 chronomail && \
    chown -R chronomail:chronomail /app
USER chronomail

# Создание необходимых директорий
RUN mkdir -p /app/logs /app/media/attachments /app/media/uploads

# Порт приложения
EXPOSE 8000

# Команда запуска
CMD ["gunicorn", "chronomail.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
