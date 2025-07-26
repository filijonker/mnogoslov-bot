import os
import telebot
import ydb # --- ИЗМЕНЕНИЕ: Простой импорт ---
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

def get_ydb_driver():
    # --- ИЗМЕНЕНИЕ: Правильный способ аутентификации для нового SDK ---
    return ydb.Driver(
        endpoint=YDB_ENDPOINT,
        database=YDB_DATABASE,
        credentials=ydb.credentials_from_str(SERVICE_ACCOUNT_KEY_JSON)
    )

def execute_ydb_query(query, params):
    driver = get_ydb_driver()
    driver.wait(timeout=5)
    
    # Новый, более простой способ работы с сессией
    with ydb.SessionPool(driver) as pool:
        return pool.retry_operation_sync(
            lambda session: session.transaction().execute(
                query,
                params,
                commit_tx=True
            )
        )

# ... (Остальной код бота НИКАК НЕ МЕНЯЕТСЯ) ...

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
    bot.reply_to(message, "Я на Render V4! Финальная версия. Пытаюсь записать в базу...")
    try:
        # Для новой библиотеки YDB нужно явно указывать тип параметра
        query = """
            DECLARE $telegram_id AS Uint64;
            UPSERT INTO users (telegram_id, goal_chars) VALUES ($telegram_id, 4000);
        """
        # Создаем типизированный параметр
        param_type = ydb.PrimitiveType.Uint64
        params = {'$telegram_id': ydb.TypedValue(int(message.from_user.id), param_type)}

        execute_ydb_query(query, params)
        bot.send_message(message.chat.id, "Тестовая запись V4 прошла успешно!")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка V4 при записи в базу: {e}")

# --- Запуск ---
if __name__ == '__main__':
    WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')
    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Вебхук установлен на {WEBHOOK_URL}")
    app.run(host='0.0.0.0', port=PORT)
