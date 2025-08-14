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

# --- Настройки и Инициализация ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DB_NAME = 'bot_database.db'
state_storage = StateMemoryStorage()
bot = TeleBot(BOT_TOKEN, state_storage=state_storage, parse_mode='Markdown')
app = Flask(__name__)

# --- Вспомогательные функции и DB ---
def get_time_string(weeks_needed):
    if weeks_needed is None or weeks_needed <= 0: return "мгновенно"
    if weeks_needed > 52:
        years = round(weeks_needed / 52, 1)
        return f"примерно {years} г." if years < 2 else f"примерно {years} лет"
    elif weeks_needed > 4:
        months = round(weeks_needed / 4.34, 1)
        return f"примерно {months} мес."
    else:
        weeks = round(weeks_needed)
        if weeks == 1: return "1 неделя"
        return f"{weeks} недели" if 2 <= weeks <= 4 else f"{weeks} недель"

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, goal_chars INTEGER, current_progress INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

# --- Вебхук ---
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

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start_command_handler(message):
    chat_id = message.chat.id
    bot.delete_state(message.from_user.id, chat_id)
    welcome_text = """*Я — бот-помощник *Многослов*. Моя задача — помочь тебе написать книгу от первого слова до последней точки. \nЧто я умею:\n- Помогу установить цель по количеству знаков и рассчитать, сколько времени потребуется для её достижения\n- Буду вести статистику прогресса\n- Подкину идею или мотивацию, если наступит ступор\n\nЧтобы начать наш писательский марафон, определим финишную черту — количество знаков, которое ты хочешь написать. Если  не знаешь точное количество, ориентируйся на любимые книги — например, в «Гарри Потере и тайной комнате» 360 000 знаков.\n\nИтак, сколько знаков ты хочешь написать в рукопись?"""
    bot.send_message(chat_id, dedent(welcome_text))
    bot.set_state(message.from_user.id, DialogStates.awaiting_goal, chat_id)

@bot.message_handler(state=DialogStates.awaiting_goal)
def handle_goal(message):
    try:
        goal = int(message.text)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data: data['goal_chars'] = goal
        bot.send_message(message.chat.id, "Отлично! А сколько дней в неделю в среднем ты планируешь писать?")
        bot.set_state(message.from_user.id, DialogStates.awaiting_days, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введи число.")

@bot.message_handler(state=DialogStates.awaiting_days)
def handle_days(message):
    try:
        days = int(message.text)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data: data['days_per_week'] = days
        bot.send_message(message.chat.id, "Понял-принял. Примерно сколько знаков за одну сессию?")
        bot.set_state(message.from_user.id, DialogStates.awaiting_chars, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введи число.")

@bot.message_handler(state=DialogStates.awaiting_chars)
def handle_chars(message):
    chat_id = message.chat.id
    try:
        chars_per_session = int(message.text)
        with bot.retrieve_data(message.from_user.id, chat_id) as data:
            goal = data['goal_chars']
            days = data['days_per_week']
        chars_per_week = days * chars_per_session
        weeks_needed = goal / chars_per_week if chars_per_week > 0 else None
        time_str = get_time_string(weeks_needed)
        final_text = f"""*Отлично, твой план готов!*\n\nТвоя цель: *{goal:,}* знаков.\nТы планируешь писать *{days}* раз в неделю по *{chars_per_session:,}* знаков.\n\nПри таком темпе, чтобы написать книгу, тебе потребуется *{time_str}*.\n\nЯ сохранил твою цель. Удачи!"""
        bot.send_message(chat_id, dedent(final_text))
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (telegram_id, goal_chars, current_progress) VALUES (?, ?, 0)", (chat_id, goal))
        conn.commit()
        conn.close()
        bot.delete_state(message.from_user.id, chat_id)
    except Exception:
        bot.send_message(chat_id, "Что-то пошло не так. /start")
        bot.delete_state(message.from_user.id, chat_id)

@bot.message_handler(state=None, commands=['stats'])
def stats_command_handler(message):
    chat_id = message.chat.id
    try:
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT current_progress, goal_chars FROM users WHERE telegram_id = ?", (chat_id,))
        result = cursor.fetchone()
        conn.close()
        if result and result[1] is not None:
            progress, goal = result
            percentage = (progress / goal * 100) if goal > 0 else 0
            stats_text = f"📊 *Твоя статистика:*\n\n*Написано:* {progress:,} / {goal:,} знаков ({percentage:.1f}%)"
            bot.send_message(chat_id, dedent(stats_text))
        else:
            bot.send_message(chat_id, "Сначала установите цель с помощью команды /start.")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")

@bot.message_handler(state=None, commands=['done'])
def done_command_handler(message):
    chat_id = message.chat.id
    try:
        args = message.text.split()
        if len(args) < 2: raise ValueError()
        added_chars = int(args[1])
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET current_progress = current_progress + ? WHERE telegram_id = ?", (added_chars, chat_id))
        if cursor.rowcount == 0:
            bot.send_message(chat_id, "Похоже, у тебя ещё не установлена цель. /start")
            conn.close()
            return
        cursor.execute("SELECT current_progress, goal_chars FROM users WHERE telegram_id = ?", (chat_id,))
        progress, goal = cursor.fetchone()
        conn.commit()
        conn.close()
        bot.send_message(chat_id, f"Отличная работа! ✨\nТвой прогресс: {progress:,} / {goal:,} знаков.")
    except (ValueError, IndexError):
        bot.send_message(chat_id, "Неверный формат. Используй: `/done 1500`")

@bot.message_handler(state=None, commands=['inspiration'])
def inspiration_command_handler(message):
    prompts = ["Твой персонаж находит загадочный артефакт...", "Опиши закат глазами...", "Начни историю с фразы..."]
    bot.send_message(message.chat.id, f"✨ *Идея для тебя:*\n\n_{random.choice(prompts)}_")

@bot.message_handler(state=None, commands=['help'])
def help_command_handler(message):
    help_text = """*Привет! Я бот Многослов. Вот что я умею:*\n\n/start ...\n/stats ...\n/done `[число]` ...\n/inspiration ..."""
    bot.send_message(message.chat.id, dedent(help_text))

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
