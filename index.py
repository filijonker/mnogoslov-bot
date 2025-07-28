import os
import telebot
import sqlite3
import json
from flask import Flask, request
from telebot import types
import datetime
import random
from textwrap import dedent # Добавлен импорт для красивого текста помощи

# --- Настройки ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DB_NAME = 'bot_database.db' # Имя файла нашей базы данных

# --- Инициализация ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Работа с базой данных SQLite ---
def init_db():
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
    # Твой отличный новый текст!
    welcome_text = """
    *✍️ Привет, я Многослов. Моя задача: помочь тебе написать книгу. Что я умею:*\n
    - Помогу установить цель по количеству знаков и рассчитать, сколько времени потребуется для её достижения
    - Буду вести статистику прогресса
    - Подкину идею или мотивацию, если наступит ступор

    Начнём?
    """
    
    # Создаем кнопку "Поставить цель"
    markup = types.InlineKeyboardMarkup()
    button_begin = types.InlineKeyboardButton("Поставить цель 🎯", callback_data="begin_setup")
    markup.add(button_begin)
    
    # Отправляем только ОДНО сообщение с текстом и кнопкой.
    # Мы не отправляем фото, так как ты этого не хотела.
    bot.send_message(chat_id, dedent(welcome_text), reply_markup=markup, parse_mode="Markdown")
    
    # ВАЖНО: Мы НЕ меняем состояние пользователя здесь. Мы ждем, пока он нажмет кнопку.

# Обработчик для кнопки "Поставить цель"
@bot.callback_query_handler(func=lambda call: call.data == 'begin_setup')
def begin_setup_callback(call):
    chat_id = call.message.chat.id
    
    # Можно отредактировать старое сообщение, чтобы было красивее
    bot.edit_message_text(
        chat_id=chat_id, 
        message_id=call.message.message_id, 
        text="Отлично! Приступим."
    )
    
    # А уже в новом сообщении задаем вопрос
    bot.send_message(chat_id, "Сколько всего знаков должно быть в твоей книге? (Например: 360000)")
    
    # И только ТЕПЕРЬ мы устанавливаем состояние, когда ждем ответа
    user_states[chat_id] = 'awaiting_goal'

# Обработчик для ответа на вопрос о цели (этот код у тебя уже есть, он идет после)
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'awaiting_goal')
def goal_handler(message):
    # ... твой код goal_handler без изменений ...

# --- НОВЫЙ БЛОК КОМАНД ИЗ МЕНЮ ---
@bot.message_handler(commands=['stats'])
def stats_handler(message):
    chat_id = message.chat.id
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT current_progress, goal_chars FROM users WHERE telegram_id = ?", (chat_id,))
        result = cursor.fetchone()
        conn.close()

        if result and result[1] is not None:
            progress, goal = result
            percentage = (progress / goal * 100) if goal > 0 else 0
            remaining = goal - progress
            
            stats_text = f"""
            📊 *Ваша статистика:*\n
            *Цель:* {goal} знаков
            *Написано:* {progress} знаков
            *Осталось:* {remaining} знаков
            *Выполнено:* {percentage:.1f}%
            """
            bot.send_message(chat_id, dedent(stats_text), parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "Сначала установите цель с помощью команды /start, чтобы я мог показать вашу статистику.")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка при получении статистики: {e}")

@bot.message_handler(commands=['inspiration'])
def inspiration_handler(message):
    prompts = [
        "Твой персонаж находит загадочный артефакт. Что это?",
        "Опиши закат глазами человека, который видит его в последний раз.",
        "Начни историю с фразы: 'Это была плохая идея с самого начала...'",
        "Два врага заперты в одной комнате. У них есть час, чтобы договориться.",
        "Цитата: 'Начинай писать, неважно о чем. Главное — двигать ручкой.' — Рэй Брэдбери",
        "Цитата: 'Секрет успеха — начать.' — Марк Твен"
    ]
    prompt = random.choice(prompts)
    bot.send_message(message.chat.id, f"✨ *Идея для тебя:*\n\n_{prompt}_", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_handler(message):
    help_text = """
    *Привет! Я бот Многослов. Вот что я умею:*\n
    /start - Начать работу и установить новую цель.
    /stats - Показать твой текущий прогресс.
    /done `[число]` - Записать `число` написанных знаков (например: `/done 2000`).
    /inspiration - Получить случайную идею или цитату для вдохновения.
    /help - Показать это сообщение.
    """
    bot.send_message(message.chat.id, dedent(help_text), parse_mode="Markdown")

# --- КОНЕЦ НОВОГО БЛОКА ---


@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'awaiting_goal')
def goal_handler(message):
    chat_id = message.chat.id
    try:
        goal = int(message.text)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (telegram_id, goal_chars, current_progress) VALUES (?, ?, 0)", (chat_id, goal))
        conn.commit()
        conn.close()
        
        bot.send_message(chat_id, f"Отлично! Твоя цель — *{goal}* знаков. Теперь ты можешь записывать свой прогресс командой `/done [число]`. Удачи!", parse_mode="Markdown")
        user_states.pop(chat_id, None) # Завершаем диалог
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введи число (например, 360000).")

@bot.message_handler(commands=['done'])
def done_handler(message):
    chat_id = message.chat.id
    try:
        args = message.text.split()
        if len(args) < 2:
            raise ValueError("Не указано количество знаков.")
            
        added_chars = int(args[1])
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET current_progress = current_progress + ? WHERE telegram_id = ?", (added_chars, chat_id))

        if cursor.rowcount == 0:
            bot.send_message(chat_id, "Похоже, у тебя еще не установлена цель. Начни с команды /start.")
            conn.close()
            return
            
        cursor.execute("SELECT current_progress, goal_chars FROM users WHERE telegram_id = ?", (chat_id,))
        progress, goal = cursor.fetchone()
        conn.commit()
        conn.close()

        percentage = (progress / goal * 100) if goal > 0 else 0
        bot.send_message(chat_id, f"Отличная работа! ✨\nТвой прогресс: {progress} / {goal} знаков ({percentage:.1f}%).")
        
    except ValueError:
        bot.send_message(chat_id, "Неверный формат. Используй: `/done 1500`")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")

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

