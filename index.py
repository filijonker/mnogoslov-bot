import os
import telebot
import ydb
import ydb.iam
import json
from flask import Flask, request
from telebot import types

# --- Настройки ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
YDB_ENDPOINT = os.environ.get('YDB_ENDPOINT')
YDB_DATABASE = os.environ.get('YDB_DATABASE')
PORT = int(os.environ.get('PORT', 8080))
# --- Новые переменные ---
SA_ID = os.environ.get('SA_ID')
SA_KEY_ID = os.environ.get('SA_KEY_ID')
SA_PRIVATE_KEY = os.environ.get('SA_PRIVATE_KEY')

# --- Инициализация ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Работа с YDB (ФИНАЛЬНАЯ ВЕРСИЯ АУТЕНТИФИКАЦИИ) ---
def get_ydb_driver():
    # Создаем credentials из отдельных компонентов. Это самый базовый способ.
    credentials = ydb.iam.ServiceAccountCredentials(
        access_key_id=SA_KEY_ID,
        service_account_id=SA_ID,
        private_key=SA_PRIVATE_KEY.encode('utf-8') # Ключ нужно передавать в байтах
    )
    return ydb.Driver(
        endpoint=YDB_ENDPOINT,
        database=YDB_DATABASE,
        credentials=credentials
    )

# execute_ydb_query остается таким же, как в v4.2
def execute_ydb_query(query, params):
    driver = get_ydb_driver()
    driver.wait(timeout=15)
    with ydb.SessionPool(driver) as pool:
        return pool.retry_operation_sync(
            lambda session: session.transaction().execute(
                query,
                params,
                commit_tx=True
            )
        )

# --- Веб-сервер и обработчики ---
@app.route('/', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Я на Render V5. Атомная аутентификация. Пробую...")
    try:
        query = "DECLARE $telegram_id AS Uint64; UPSERT INTO users (telegram_id, goal_chars) VALUES ($telegram_id, 5000);"
        param_type = ydb.PrimitiveType.Uint64
        params = {'$telegram_id': ydb.TypedValue(int(message.from_user.id), param_type)}
        execute_ydb_query(query, params)
        bot.send_message(message.chat.id, "ЗАПИСЬ V5 ПРОШЛА УСПЕШНО!")
    except Exception as e:
        # Выводим максимально подробную ошибку
        import traceback
        error_text = traceback.format_exc()
        bot.send_message(message.chat.id, f"Ошибка V5: {e}\n\n{error_text}")

# --- Запуск ---
if __name__ == '__main__':
    WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')
    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Вебхук установлен на {WEBHOOK_URL}")
    app.run(host='0.0.0.0', port=PORT)
