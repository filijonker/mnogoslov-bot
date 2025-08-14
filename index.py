import os
import telebot
import sqlite3
import json
from flask import Flask, request
from telebot import types, TeleBot
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import random
from textwrap import dedent

# --- Настройки и Инициализация (все как было) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DB_NAME = 'bot_database.db'
state_storage = StateMemoryStorage()
bot = TeleBot(BOT_TOKEN, state_storage=state_storage, parse_mode='Markdown')
app = Flask(__name__)

# --- Вспомогательные функции и DB (все как было) ---
def get_time_string(weeks_needed):
    if weeks_needed is None or weeks_needed <= 0: return "мгновенно"
    if weeks_needed > 52: return f"~{round(weeks_needed / 52, 1)} г."
    if weeks_needed > 4: return f"~{round(weeks_needed / 4.34, 1)} мес."
    weeks = round(weeks_needed)
    if weeks == 1: return "1 неделя"
    return f"{weeks} недели"

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, goal_chars INTEGER, current_progress INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

# --- Вебхук (все как было) ---
@app.route('/', methods=['POST'])
def process_webhook():
    json_str = request.get_data().decode('utf-8')
    update = types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

# --- Состояния ---
class DialogStates(StatesGroup):
    awaiting_goal = State()
    awaiting_days = State()
    awaiting_chars = State()

# --- ОБРАБОТЧИКИ (НОВАЯ, ПРОСТАЯ СТРУКТУРА) ---

# 1. Обработчик /start. Он один, и он просто начинает диалог.
@bot.message_handler(commands=['start'])
def start_command_handler(message):
    chat_id = message.chat.id
    bot.delete_state(message.from_user.id, chat_id) # На всякий случай сбрасываем старое состояние
    welcome_text = """
    Привет! Я — Многослов. Моя задача — помочь тебе написать книгу...
    ...Итак, сколько знаков ты хочешь написать в рукопись?
    """
    bot.send_message(chat_id, dedent(welcome_text))
    bot.set_state(message.from_user.id, DialogStates.awaiting_goal, chat_id)

# 2. Обработчики состояний диалога (идут следом)
@bot.message_handler(state=DialogStates.awaiting_goal)
def handle_goal(message):
    #... (код из твоего goal_handler)
    try:
        goal = int(message.text)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['goal_chars'] = goal
        bot.send_message(message.chat.id, "Отлично! А сколько дней в неделю...")
        bot.set_state(message.from_user.id, DialogStates.awaiting_days, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введи число.")

@bot.message_handler(state=DialogStates.awaiting_days)
def handle_days(message):
    #... (код из твоего days_handler)
    try:
        days = int(message.text)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['days_per_week'] = days
        bot.send_message(message.chat.id, "Понял-принял. А сколько примерно знаков за одну сессию?")
        bot.set_state(message.from_user.id, DialogStates.awaiting_chars, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введи число.")

@bot.message_handler(state=DialogStates.awaiting_chars)
def handle_chars(message):
    #... (код из твоего chars_handler, с расчетом и сохранением в базу)
    chat_id = message.chat.id
    try:
        chars_per_session = int(message.text)
        with bot.retrieve_data(message.from_user.id, chat_id) as data:
            goal = data['goal_chars']
            days = data['days_per_week']
        chars_per_week = days * chars_per_session
        weeks_needed = goal / chars_per_week if chars_per_week > 0 else None
        time_str = get_time_string(weeks_needed)
        final_text = f"""*Отлично, твой план готов!*\n\nТвоя цель: *{goal:,}* знаков..."""
        bot.send_message(chat_id, dedent(final_text))
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (telegram_id, goal_chars, current_progress) ...", (chat_id, goal))
        conn.commit()
        conn.close()
        bot.delete_state(message.from_user.id, chat_id)
    except Exception:
        bot.send_message(chat_id, "Что-то пошло не так. /start")
        bot.delete_state(message.from_user.id, chat_id)

# 3. Обработчики для остальных команд (теперь state=None, то есть работают только вне диалога)
@bot.message_handler(state=None, commands=['stats'])
def stats_command_handler(message):
    # ... (твой код из stats_handler)
    chat_id = message.chat.id
    # ...

@bot.message_handler(state=None, commands=['done'])
def done_command_handler(message):
    # ... (твой код из done_handler)
    chat_id = message.chat.id
    # ...

@bot.message_handler(state=None, commands=['inspiration'])
def inspiration_command_handler(message):
    # ... (твой код из inspiration_handler)

@bot.message_handler(state=None, commands=['help'])
def help_command_handler(message):
    # ... (твой код из help_handler)

# --- Запуск ---
if __name__ == '__main__':
    print("Инициализирую базу данных...")
    init_db()
    print("База данных готова.")
    if 'RENDER' in os.environ:
        print("Запускаю бота в режиме вебхука...")
        WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')
        if WEBHOOK_URL:
            bot.remove_webhook()
            bot.set_webhook(url=WEBHOOK_URL)
            print(f"Вебхук установлен на {WEBHOOK_URL}")
        app.run(host='0.0.0.0', port=PORT)
    else:
        print("Запускаю бота в режиме polling...")
        bot.remove_webhook()
        bot.polling(none_stop=True)
