import os
import telebot
from flask import Flask, request

# --- Минимальные настройки ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Единственный обработчик ---
@bot.message_handler(commands=['start'])
def start_reply(message):
    bot.send_message(message.chat.id, "Я ЖИВОЙ И ОТВЕЧАЮ НА /start!")

# --- Вебхук ---
@app.route('/', methods=['POST'])
def process_webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return 'ok', 200
    except Exception as e:
        print(f"!!! ОШИБКА В ВЕБХУКЕ: {e}")
        return 'error', 500

# --- Запуск ---
if __name__ == '__main__':
    if 'RENDER' in os.environ:
        WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Тестовый вебхук установлен на {WEBHOOK_URL}")
        app.run(host='0.0.0.0', port=PORT)
