import os
import telebot
import sqlite3
import json
from flask import Flask, request
from telebot import types, TeleBot
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage  # Импортируем хранилище состояний
import random
from textwrap import dedent

# --- Настройки ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DB_NAME = 'bot_database.db'

# --- Инициализация с FSM ---
state_storage = StateMemoryStorage()
bot = TeleBot(BOT_TOKEN, state_storage=state_storage) # Передаем хранилище в бота
app = Flask(__name__)

# --- Вспомогательная функция для времени ---
def get_time_string(weeks_needed):
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

# --- Работа с базой данных ---
def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
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
    update = types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

# --- ОПИСАНИЕ СОСТОЯНИЙ ДИАЛОГА ---
class DialogStates(StatesGroup):
    awaiting_goal = State()
    awaiting_days_per_week = State()
    awaiting_chars_per_session = State()

# --- Главная логика бота ---

# Обработчик, который прерывает любой диалог по команде
@bot.message_handler(state='*', commands=['start'])
def interrupt_and_start(message):
    bot.delete_state(message.from_user.id, message.chat.id)
    start_handler(message) # Вызываем основной обработчик /start

# Основной обработчик для /start (теперь без state)
def start_handler(message):
    chat_id = message.chat.id
    # Твой прекрасный текст
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
    # Устанавливаем первое состояние через FSM
    bot.set_state(message.from_user.id, DialogStates.awaiting_goal, chat_id)


# --- Обработчики состояний диалога ---

@bot.message_handler(state=DialogStates.awaiting_goal)
def goal_handler(message):
    chat_id = message.chat.id
    try:
        goal = int(message.text)
        with bot.retrieve_data(message.from_user.id, chat_id) as data:
            data['goal_chars'] = goal
        
        bot.send_message(chat_id, "Отлично! А сколько дней в неделю в среднем ты планируешь писать?")
        bot.set_state(message.from_user.id, DialogStates.awaiting_days_per_week, chat_id)
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введи число.")

@bot.message_handler(state=DialogStates.awaiting_days_per_week)
def days_handler(message):
    chat_id = message.chat.id
    try:
        days = int(message.text)
        with bot.retrieve_data(message.from_user.id, chat_id) as data:
            data['days_per_week'] = days
        bot.send_message(chat_id, "Понял-принял. Примерно сколько знаков за одну сессию?")
        bot.set_state(message.from_user.id, DialogStates.awaiting_chars_per_session, chat_id)
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введи число (например, 7).")

@bot.message_handler(state=DialogStates.awaiting_chars_per_session)
def chars_handler(message):
    chat_id = message.chat.id
    try:
        chars_per_session = int(message.text)
        with bot.retrieve_data(message.from_user.id, chat_id) as data:
            goal = data['goal_chars']
            days = data['days_per_week']
        
        chars_per_week = days * chars_per_session
        weeks_needed = goal / chars_per_week if chars_per_week > 0 else None
        time_str = get_time_string(weeks_needed)
        
        final_text = f"""
        *Отлично, твой план готов!*
        
        Твоя цель: *{goal:,}* знаков.
        Ты планируешь писать *{days}* раз в неделю по *{chars_per_session:,}* знаков.
        
        При таком темпе, чтобы написать книгу, тебе потребуется *{time_str}*.
        
        Я сохранил твою цель. Ну что, пора начинать? Когда напишешь сколько-нибудь знаков, возвращайся и запиши прогресс командой `/done [кол-во знаков]`.
        """
        bot.send_message(chat_id, dedent(final_text), parse_mode="Markdown")
        
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (telegram_id, goal_chars, current_progress) VALUES (?, ?, 0)", (chat_id, goal))
        conn.commit()
        conn.close()
        
        bot.delete_state(message.from_user.id, chat_id)
    except (ValueError, KeyError, TypeError):
        bot.send_message(chat_id, "Что-то пошло не так. Давай начнем сначала? /start")
        bot.delete_state(message.from_user.id, chat_id)

# --- Команды из меню (работают из любого состояния) ---

@bot.message_handler(state='*', commands=['stats', 'inspiration', 'help', 'done'])
def general_commands_handler(message):
    chat_id = message.chat.id
    # Прерываем любой диалог, если он был
    bot.delete_state(message.from_user.id, chat_id)

    if message.text.startswith('/stats'):
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
                stats_text = f"📊 *Твоя статистика:*\n\n*Цель:* {goal:,} знаков...\n..."
                bot.send_message(chat_id, dedent(stats_text), parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "Привет! Чтобы начать, введи /start")
        except Exception as e:
            bot.send_message(chat_id, f"Произошла ошибка: {e}")
            
    elif message.text.startswith('/inspiration'):
        prompts = ["Твой персонаж находит...", "...в последний раз.", "...с самого начала..."]
        bot.send_message(chat_id, f"✨ *Идея для тебя:*\n\n_{random.choice(prompts)}_", parse_mode="Markdown")

    elif message.text.startswith('/help'):
        help_text = """*Привет! Я бот Многослов. Вот что я умею:*\n\n/start ..."""
        bot.send_message(chat_id, dedent(help_text), parse_mode="Markdown")
        
    elif message.text.startswith('/done'):
        try:
            args = message.text.split()
            if len(args) < 2: raise ValueError("Не указано количество знаков.")
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
