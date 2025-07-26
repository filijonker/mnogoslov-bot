import os
import telebot
import sqlite3 # Встроенная библиотека, ничего устанавливать не нужно!
import json
from flask import Flask, request
from telebot import types
import datetime

# --- Настройки ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DB_NAME = 'bot_database.db' # Имя файла нашей базы данных

# --- Инициализация ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Работа с базой данных SQLite ---
def init_db():
    """Создает таблицу, если ее еще нет."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            goal_chars INTEGER,
            current_progress INTEGER DEFAULT 0,
            schedule_days TEXT,
            schedule_time TEXT,
            reminders_on INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# --- Веб-сервер и Вебхук ---
@app.route('/', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

# --- Главная логика бота ---

# Словарь для хранения состояний диалога
user_states = {}

@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Привет! Я бот Многослов. Я снова в строю и готов работать. Давай рассчитаем твой план. Сколько всего знаков в твоей книге?")
    user_states[chat_id] = 'awaiting_goal'

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'awaiting_goal')
def goal_handler(message):
    chat_id = message.chat.id
    try:
        goal = int(message.text)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Сохраняем пользователя и его цель
        cursor.execute("INSERT OR REPLACE INTO users (telegram_id, goal_chars) VALUES (?, ?)", (chat_id, goal))
        conn.commit()
        conn.close()
        
        bot.send_message(chat_id, "Отлично! Теперь введи свой ежедневный план в знаках (например, 2000).")
        user_states[chat_id] = 'awaiting_daily_plan'
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введи число.")

# ... Мы можем добавить остальную логику диалога сюда позже ...
# Сейчас главное, чтобы это заработало!

# Команда для записи прогресса
@bot.message_handler(commands=['done'])
def done_handler(message):
    chat_id = message.chat.id
    try:
        # Получаем количество написанных знаков из сообщения
        added_chars = int(message.text.split()[1])
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Обновляем прогресс
        cursor.execute("UPDATE users SET current_progress = current_progress + ? WHERE telegram_id = ?", (added_chars, chat_id))
        # Получаем новый прогресс и цель
        cursor.execute("SELECT current_progress, goal_chars FROM users WHERE telegram_id = ?", (chat_id,))
        progress, goal = cursor.fetchone()
        conn.commit()
        conn.close()

        percentage = (progress / goal * 100) if goal > 0 else 0
        bot.send_message(chat_id, f"Отличная работа! ✨\nТвой прогресс: {progress} / {goal} знаков ({percentage:.1f}%).")
        
    except (IndexError, ValueError):
        bot.send_message(chat_id, "Неверный формат. Используй: /done 1500")

# --- Запуск ---
if __name__ == '__main__':
    print("Инициализирую базу данных...")
    init_db()
    print("База данных готова.")
    
    WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')
    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Вебхук установлен на {WEBHOOK_URL}")
    
    app.run(host='0.0.0.0', port=PORT)
