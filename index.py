import os
import telebot
import sqlite3
import json
from flask import Flask, request
from telebot import types
import random
from textwrap import dedent

# --- Настройки ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DB_NAME = 'bot_database.db' 

# --- Вспомогательная функция для времени ---
def get_time_string(weeks_needed):
    """Превращает недели в красивую строку (недели, месяцы, годы)."""
    if weeks_needed is None or weeks_needed <= 0:
        return "мгновенно (или проверьте введенные данные)"
    
    if weeks_needed > 52:
        years = round(weeks_needed / 52, 1)
        return f"примерно {years} г." if years < 2 else f"примерно {years} лет"
    elif weeks_needed > 4:
        months = round(weeks_needed / 4.34, 1)
        return f"примерно {months} мес."
    else:
        weeks = round(weeks_needed)
        if weeks == 1: return "1 неделя"
        if 2 <= weeks <= 4: return f"{weeks} недели"
        return f"{weeks} недель"

# --- Инициализация ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Работа с базой данных SQLite ---
def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    # Упрощенная таблица без полей для напоминаний
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            goal_chars INTEGER,
            current_progress INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# --- Веб-сервер и Вебхук ---
@app.route('/', methods=['POST'])
def process_webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

# --- Главная логика бота ---
user_states = {} # Простой словарь для короткого диалога

@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    welcome_text = """
Привет! Я — Многослов. Моя задача — помочь тебе написать книгу от первого слова до последней точки. 

Что я умею:
● Помогу установить цель по количеству знаков и рассчитать, сколько времени потребуется для её достижения
● Буду вести статистику прогресса
● Подкину идею или мотивацию, если наступит ступор

Чтобы начать наш писательский марафон, определим финишную черту — количество знаков, которое ты хочешь написать. Если  не знаешь точное количество, ориентируйся на любимые книги — например, в «Гарри Потере и тайной комнате» 360 000 знаков.

Итак, сколько знаков ты хочешь написать в рукопись?

    """
    bot.send_message(chat_id, dedent(welcome_text), parse_mode="Markdown")
    user_states[chat_id] = 'awaiting_goal'

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'awaiting_goal')
def goal_handler(message):
    chat_id = message.chat.id
    try:
        goal = int(message.text)
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (telegram_id, goal_chars, current_progress) VALUES (?, ?, 0)", (chat_id, goal))
        conn.commit()
        conn.close()
        
        # Простое завершение диалога, без кнопок и вопросов
        bot.send_message(chat_id, f"Отлично! Твоя цель — *{goal:,}* знаков. Когда напишешь сколько-то знаков в рукопись, возвращайся сюда, чтобы отметить прогресс. Напиши команду`/done [количество знаков]`. Удачи!", parse_mode="Markdown")
        user_states.pop(chat_id, None) 
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введи число (например, 360000).")

# --- Команды из меню ---

@bot.message_handler(commands=['stats'])
def stats_handler(message):
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
            remaining = goal - progress
            stats_text = f"""📊 *Твоя статистика:*\n\n*Цель:* {goal:,} знаков\n*Написано:* {progress:,} знаков\n*Осталось:* {remaining:,} знаков\n*Выполнено:* {percentage:.1f}%"""
            bot.send_message(chat_id, dedent(stats_text), parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "Сначала установите цель с помощью команды /start.")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")

@bot.message_handler(commands=['inspiration'])
def inspiration_handler(message):
    prompts = ["Твой персонаж находит загадочный артефакт. Что это?", "Опиши закат глазами человека, который видит его в последний раз.", "Начни историю с фразы: 'Это была плохая идея с самого начала...'"]
    prompt = random.choice(prompts)
    bot.send_message(message.chat.id, f"✨ *Идея для тебя:*\n\n_{prompt}_", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_handler(message):
    help_text = """*Привет! Я бот Многослов. Вот что я умею:*\n\n/start - Начать работу и установить новую цель.\n/stats - Показать твой текущий прогресс.\n/done `[число]` - Записать `число` написанных знаков (например: `/done 2000`).\n/inspiration - Получить случайную идею или цитату для вдохновения."""
    bot.send_message(chat_id, dedent(help_text), parse_mode="Markdown")

@bot.message_handler(commands=['done'])
def done_handler(message):
    chat_id = message.chat.id
    try:
        args = message.text.split()
        if len(args) < 2: raise ValueError("Не указано количество знаков.")
        added_chars = int(args[1])
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT goal_chars FROM users WHERE telegram_id = ?", (chat_id,))
        if cursor.fetchone() is None:
            bot.send_message(chat_id, "Похоже, у тебя ещё не установлена цель. Начни с команды /start.")
            conn.close()
            return
        cursor.execute("UPDATE users SET current_progress = current_progress + ? WHERE telegram_id = ?", (added_chars, chat_id))
        cursor.execute("SELECT current_progress, goal_chars FROM users WHERE telegram_id = ?", (chat_id,))
        progress, goal = cursor.fetchone()
        conn.commit()
        conn.close()
        percentage = (progress / goal * 100) if goal > 0 else 0
        bot.send_message(chat_id, f"Отличная работа! ✨\nТвой прогресс: {progress:,} / {goal:,} знаков ({percentage:.1f}%).")
    except ValueError:
        bot.send_message(chat_id, "Неверный формат. Используй: `/done 1500`")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")

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
