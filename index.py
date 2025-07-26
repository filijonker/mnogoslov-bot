import os
import telebot
# --- ИЗМЕНЕНИЕ: Импортируем компоненты по полному пути ---
from yandex.cloud.ydb import (
    Ydb,
    Driver,
    DriverConfig,
    construct_credentials_from_service_account_key,
)
import json
from flask import Flask, request
from telebot import types

# --- Настройки (без изменений) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
YDB_ENDPOINT = os.environ.get('YDB_ENDPOINT')
YDB_DATABASE = os.environ.get('YDB_DATABASE')
PORT = int(os.environ.get('PORT', 8080))
SERVICE_ACCOUNT_KEY_JSON = os.environ.get('SERVICE_ACCOUNT_KEY_JSON') 

# --- Инициализация ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Работа с YDB (с изменениями) ---
def get_ydb_driver():
    # Используем импортированные функции
    credentials = construct_credentials_from_service_account_key(SERVICE_ACCOUNT_KEY_JSON)
    driver_config = DriverConfig(
        endpoint=YDB_ENDPOINT,
        database=YDB_DATABASE,
        credentials=credentials
    )
    return Driver(driver_config)

def execute_ydb_query(query, params):
    driver = get_ydb_driver()
    driver.wait(timeout=5)
    # --- ИЗМЕНЕНИЕ: Используем with, это более надежно ---
    with Driver(get_ydb_driver().endpoint, get_ydb_driver().database, get_ydb_driver().credentials) as driver:
       with Ydb(driver) as ydb_client:
          session = ydb_client.table_client.session().create()
          prepared_query = session.prepare(query)
          session.transaction().execute(prepared_query, params, commit_tx=True)


# ... (Остальной код бота, вебхука и обработчиков остается таким же, как в прошлый раз) ...

# --- Веб-сервер и Вебхук ---
@app.route('/', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

# --- Главная логика бота ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Я на Render V3! Пытаюсь записать в базу...")
    try:
        query = """
            DECLARE $telegram_id AS Uint64;
            UPSERT INTO users (telegram_id, goal_chars) VALUES ($telegram_id, 3000);
        """
        params = {'$telegram_id': int(message.from_user.id)}
        execute_ydb_query(query, params)
        bot.send_message(message.chat.id, "Тестовая запись V3 прошла успешно!")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка V3 при записи в базу: {e}")

# --- Запуск ---
if __name__ == '__main__':
    WEBHOOK_URL = f"{os.environ.get('RENDER_EXTERNAL_URL')}"
    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Вебхук установлен на {WEBHOOK_URL}")
    app.run(host='0.0.0.0', port=PORT)
