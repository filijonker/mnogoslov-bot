import os
import telebot
import sqlite3
import json
from flask import Flask, request
from telebot import types
import random
from textwrap import dedent

# --- Настройки и Инициализация (без изменений) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DB_NAME = 'bot_database.db' 
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Функции для работы с БД и временем (без изменений) ---
def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, goal_chars INTEGER, current_progress INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

def get_time_string(weeks_needed):
    if weeks_needed is None or weeks_needed <= 0: return "мгновенно (или проверьте введенные данные)"
    if weeks_needed > 52:
        years = round(weeks_needed / 52, 1)
        return f"примерно {years} г." if years < 5 else f"примерно {years} лет"
    elif weeks_needed > 4:
        months = round(weeks_needed / 4.34, 1)
        return f"примерно {months} мес."
    else:
        weeks = round(weeks_needed)
        if weeks == 1: return "1 неделя"
        return f"{weeks} недели"

# --- Веб-сервер (без изменений) ---
@app.route('/', methods=['POST'])
def process_webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

# --- Главная логика бота ---
user_states = {}

# --- ИЗМЕНЕНИЕ: Сначала все обработчики КОМАНД ---

@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    welcome_text = """*Я — бот-помощник *Многослов*. Моя задача — помочь тебе написать книгу от первого слова до последней точки. \nЧто я умею:\n- Помогу установить цель по количеству знаков и рассчитать, сколько времени потребуется для её достижения\n- Буду вести статистику прогресса\n- Подкину идею или мотивацию, если наступит ступор\n\nЧтобы начать наш писательский марафон, определим финишную черту — количество знаков, которое ты хочешь написать. Если  не знаешь точное количество, ориентируйся на любимые книги — например, в «Гарри Потере и тайной комнате» 360 000 знаков.\n\nТеперь введи числом, сколько знаков будет в твоей книге (пример: 200 000)"""
    bot.send_message(chat_id, dedent(welcome_text), parse_mode="Markdown")
    user_states[chat_id] = 'awaiting_goal'

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
            stats_text = f"📊 *Ваша статистика:*\n\n*Цель:* {goal:,} знаков\n*Написано:* {progress:,} знаков\n*Осталось:* {remaining:,} знаков\n*Выполнено:* {percentage:.1f}%"
            bot.send_message(chat_id, dedent(stats_text), parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "Привет! Я Многослов и я помогу тебе написать книгу. Чтобы начать, введи /start")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")

@bot.message_handler(commands=['inspiration'])
def inspiration_handler(message):
    prompts = ["Твой персонаж находит загадочный артефакт. Что это?", "Опиши закат глазами человека, который видит его в последний раз.", "Начни историю с фразы: 'Это была плохая идея с самого начала...'"]
    prompt = random.choice(prompts)
    bot.send_message(message.chat.id, f"✨ *Идея для тебя:*\n\n_{prompt}_", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_handler(message):
    help_text = "*Привет! Я бот Многослов. Вот что я умею:*\n\n/start - Начать работу и установить новую цель.\n/stats - Показать твой текущий прогресс.\n/done `[число]` - Записать `число` написанных знаков (например: `/done 2000`).\n/inspiration - Получить случайную идею или цитату для вдохновения."
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

# --- Теперь обработчики состояний диалога ---

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'awaiting_goal')
def goal_handler(message):
    chat_id = message.chat.id
    try:
        goal = int(message.text)
        user_states[chat_id] = {'state': 'awaiting_days_per_week', 'goal_chars': goal}
        bot.send_message(chat_id, "Отлично! А сколько дней в неделю в среднем ты планируешь писать?")
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введи число.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('state') == 'awaiting_days_per_week')
def days_handler(message):
    chat_id = message.chat.id
    try:
        days = int(message.text)
        user_states[chat_id]['days_per_week'] = days
        user_states[chat_id]['state'] = 'awaiting_chars_per_session'
        bot.send_message(chat_id, "Понял-принял. Примерно сколько знаков за одну сессию?")
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введи число (например, 7).")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('state') == 'awaiting_chars_per_session')
def chars_handler(message):
    chat_id = message.chat.id
    try:
        session_data = user_states[chat_id]
        goal = session_data['goal_chars']
        days = session_data['days_per_week']
        chars_per_session = int(message.text)
        chars_per_week = days * chars_per_session
        weeks_needed = goal / chars_per_week if chars_per_week > 0 else None
        time_str = get_time_string(weeks_needed)
        final_text = f"""*Отлично, твой план готов!*\n\nТвоя цель: *{goal:,}* знаков.\nТы планируешь писать *{days}* раз в неделю по *{chars_per_session:,}* знаков.\n\nПри таком темпе, чтобы написать книгу, тебе потребуется *{time_str}*.\n\nЯ сохранил твою цель. Ну что, пора начинать? Когда напишешь сколько-нибудь знаков, возвращайся и запиши прогресс командой `/done [кол-во знаков]`."""
        bot.send_message(chat_id, dedent(final_text), parse_mode="Markdown")
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (telegram_id, goal_chars, current_progress) VALUES (?, ?, 0)", (chat_id, goal))
        conn.commit()
        conn.close()
        user_states.pop(chat_id, None)
    except (ValueError, KeyError):
        bot.send_message(chat_id, "Что-то пошло не так. Давай начнем сначала? /start")
        
# --- И только в самом конце — обработчик "всего остального" ---
@bot.message_handler(func=lambda message: True)
def handle_unknown_messages(message):
    unknown_text = """Хм, я не совсем понял. 🤔\n\nЯ пока умею отвечать только на команды из *Меню*. \n\nНажми /help, чтобы посмотреть список того, что я умею."""
    bot.send_message(message.chat.id, dedent(unknown_text), parse_mode="Markdown")

# --- Запуск (без изменений) ---
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

