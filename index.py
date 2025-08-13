import os
import telebot
import sqlite3
import json
from flask import Flask, request
from telebot import types, TeleBot
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from textwrap import dedent
import random

# --- Настройки ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DB_NAME = 'bot_database.db'

# --- Инициализация с FSM ---
state_storage = StateMemoryStorage()
bot = TeleBot(BOT_TOKEN, state_storage=state_storage, parse_mode='Markdown')
app = Flask(__name__)

# --- База данных ---
def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, goal_chars INTEGER, current_progress INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

# --- Вебхук ---
@app.route('/', methods=['POST'])
def process_webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return 'ok', 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return 'error', 500

# --- Описание состояний диалога ---
class DialogStates(StatesGroup):
    awaiting_goal = State()
    awaiting_days = State()
    awaiting_chars = State()

# --- Обработчик /start, который НАЧИНАЕТ диалог ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    welcome_text = "*Я — бот-помощник *Многослов*...*\n\n...Теперь введи числом, сколько знаков будет в твоей книге?"
    bot.send_message(chat_id, dedent(welcome_text))
    bot.set_state(message.from_user.id, DialogStates.awaiting_goal, chat_id)

# --- Обработчики для каждого состояния диалога ---
@bot.message_handler(state=DialogStates.awaiting_goal)
def goal_handler(message):
    try:
        goal = int(message.text)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['goal_chars'] = goal
        bot.send_message(message.chat.id, "Отлично! А сколько дней в неделю ты планируешь писать?")
        bot.set_state(message.from_user.id, DialogStates.awaiting_days, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введи число.")

@bot.message_handler(state=DialogStates.awaiting_days)
def days_handler(message):
    try:
        days = int(message.text)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['days_per_week'] = days
        bot.send_message(message.chat.id, "Понял. А сколько знаков за одну сессию?")
        bot.set_state(message.from_user.id, DialogStates.awaiting_chars, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введи число.")

@bot.message_handler(state=DialogStates.awaiting_chars)
def chars_handler(message):
    chat_id = message.chat.id
    try:
        with bot.retrieve_data(message.from_user.id, chat_id) as data:
            goal = data['goal_chars']
            days = data['days_per_week']
        
        # ... (здесь нужен будет твой код для расчета времени)
        final_text = f"*Отлично, твой план готов!* Цель: {goal} знаков."
        bot.send_message(chat_id, dedent(final_text))

        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (telegram_id, goal_chars) VALUES (?, ?)", (chat_id, goal))
        conn.commit()
        conn.close()

        bot.delete_state(message.from_user.id, chat_id)
    except (ValueError, KeyError):
        bot.send_message(chat_id, "Что-то пошло не так. /start")
        bot.delete_state(message.from_user.id, chat_id)

# --- Остальные команды ---
@bot.message_handler(state="*", commands=['stats', 'done', 'help', 'inspiration'])
def commands_handler(message):
    bot.delete_state(message.from_user.id, message.chat.id) # Прерываем любой диалог
    if message.text.startswith('/stats'):
        # Здесь должен быть твой код для stats_handler
        bot.send_message(message.chat.id, "Здесь будет статистика...")
    # ... и так далее для других команд

# --- Запуск ---
if __name__ == '__main__':
    init_db()
    if 'RENDER' in os.environ:
        WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Вебхук установлен на {WEBHOOK_URL}")
        app.run(host='0.0.0.0', port=PORT)
    else:
        bot.remove_webhook()
        bot.polling(none_stop=True)
