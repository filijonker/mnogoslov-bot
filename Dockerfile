# Шаг 1: Берем официальный готовый образ Python 3.9
FROM cr.yandex/yc/yandex-cloud-sdk:latest

# Шаг 2: Создаем рабочую папку внутри контейнера
WORKDIR /app

# Шаг 3: Копируем туда наш список зависимостей
COPY requirements.txt .

# Шаг 4: Устанавливаем все зависимости из списка
RUN pip install --no-cache-dir -r requirements.txt

# Шаг 5: Копируем ВЕСЬ остальной код (наш index.py) в рабочую папку
COPY . .

# Шаг 6: Указываем, какую команду запустить, когда контейнер стартует
CMD ["python", "index.py"]