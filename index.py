import os
import telebot
import ydb
from flask import Flask, request
from telebot import types

# --- Настройки ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
YDB_ENDPOINT = os.environ.get('YDB_ENDPOINT')
YDB_DATABASE = os.environ.get('YDB_DATABASE')
PORT = int(os.environ.get('PORT', 8080))
# URL для установки вебхука. Мы его получим от Яндекса.
# Но для безопасности лучше передавать его тоже через переменную окружения.
WEBHOOK_URL = os.environ.get('WEBHOOK_URL') 

# --- Инициализация ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Работа с YDB (как мы и планировали) ---
def execute_ydb_query(query, params):
    driver = ydb.Driver(endpoint=YDB_ENDPOINT, database=YDB_DATABASE)
    driver.wait(timeout=5)
    pool = ydb.SessionPool(driver)
    
    def execute_in_pool(session):
        prepared_query = session.prepare(query)
        session.transaction(ydb.SerializableReadWrite()).execute(
            prepared_query,
            params,
            commit_tx=True
        )
    return pool.retry_operation_sync(execute_in_pool)

# --- Веб-сервер и Вебхук ---
@app.route('/', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

# --- Главная логика бота ---
# Мы вернем сюда всю нашу сложную логику, когда убедимся,
# что бот запускается в контейнере.
@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Просто тестовый ответ для проверки
    bot.reply_to(message, "Я в контейнере V2.0! И я живой! База данных подключена.")
    
    # Попытка записать что-то в базу для проверки
    try:
        query = """
            DECLARE $telegram_id AS Uint64;
            UPSERT INTO users (telegram_id, goal_chars) VALUES ($telegram_id, 100);
        """
        params = {'$telegram_id': message.from_user.id}
        execute_ydb_query(query, params)
        bot.send_message(message.chat.id, "Тестовая запись в базу данных прошла успешно!")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при записи в базу: {e}")

# --- Запуск ---
if __name__ == '__main__':
    print("Бот запускается...")
    # Устанавливаем вебхук при старте
    bot.remove_webhook()
    # Важно! Убедитесь, что WEBHOOK_URL установлен в переменных окружения контейнера
    if WEBHOOK_URL:
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Вебхук установлен на {WEBHOOK_URL}")
    else:
        print("Переменная WEBHOOK_URL не установлена, вебхук не настроен.")
        
    app.run(host='0.0.0.0', port=PORT)
