# Шаг 1: Берем официальный Python 3.9. Это самый надежный образ.
FROM python:3.9-slim

# ШАГ 1.5: Устанавливаем системные зависимости, необходимые для yandex-ydb
# Это то, чего нам не хватало!
RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ \
    make \
    cmake \
    libssl-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Шаг 2: Создаем рабочую папку
WORKDIR /app

# Шаг 3: Копируем список библиотек
COPY requirements.txt .

# Шаг 4: Устанавливаем библиотеки. Теперь все должно получиться!
RUN pip install --no-cache-dir -r requirements.txt

# Шаг 5: Копируем наш код
COPY . .

# Шаг 6: Запускаем бота
CMD ["python", "index.py"]
