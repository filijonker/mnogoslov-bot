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
DB_NAME = 'bot_database.db' # Имя файла нашей базы данных

# --- Инициализация ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Работа с базой данных SQLite ---
def init_db():
    """Создает таблицу в базе данных, если она еще не существует."""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            state TEXT,
            goal_chars INTEGER,
            current_progress INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# --- Веб-сервер и Вебхук ---
@app.route('/', methods=['POST'])
def process_webhook():
    """Принимает обновления от Telegram и передает их в Telebot."""
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        # ВАЖНО: telebot ожидает СПИСОК обновлений.
        # Мы передаем ему список из одного элемента.
        bot.process_new_updates([update])
        return 'ok', 200
    except Exception as e:
        print(f"Webhook processing error: {e}")
        return 'error', 500

# --- Главная логика бота ---

# Мы больше не используем словарь user_states.
# Вместо этого мы будем хранить состояние прямо в базе данных.
def get_user_state(chat_id):
    """Получает состояние пользователя из базы данных."""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT state FROM users WHERE telegram_id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_user_state(chat_id, state):
    """Устанавливает состояние пользователя в базе данных."""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (telegram_id, state) VALUES (?, ?)", (chat_id, state))
    conn.commit()
    conn.close()

@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    welcome_text = """
    *✍️ Привет, я Многослов. Моя задача: помочь тебе написать книгу. Что я умею:*\n
    - Помогу установить цель по количеству знаков.
    - Буду вести статистику твоего прогресса.
    - Подкину идею или мотивацию, если наступит ступор.

    Начнём?
    """
    
    markup = types.InlineKeyboardMarkup()
    button_begin = types.InlineKeyboardButton("Поставить цель 🎯", callback_data="begin_setup")
    markup.add(button_begin)
    
    bot.send_message(chat_id, dedent(welcome_text), reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'begin_setup')
def begin_setup_callback(call):
    chat_id = call.message.chat.id
    bot.edit_message_text(
        chat_id=chat_id, 
        message_id=call.message.message_id, 
        text="Отлично! Приступим.",
        reply_markup=None
    )
    bot.send_message(chat_id, "Сколько всего знаков должно быть в твоей книге? (Например: 360000)")
    set_user_state(chat_id, 'awaiting_goal')

@bot.message_handler(func=lambda message: get_user_state(message.chat.id) == 'awaiting_goal')
def goal_handler(message):
    chat_id = message.chat.id
    try:
        goal = int(message.text)
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        # Обновляем цель для существующего пользователя
        cursor.execute("UPDATE users SET goal_chars = ?, current_progress = 0, state = NULL WHERE telegram_id = ?", (goal, chat_id))
        conn.commit()
        conn.close()
        
        bot.send_message(chat_id, f"Отлично! Твоя цель — *{goal:,}* знаков. Теперь ты можешь записывать свой прогресс командой `/done [число]`. Удачи!", parse_mode="Markdown")
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введи число (например, 360000).")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка при сохранении цели: {e}")

# ... (здесь будут остальные обработчики: /stats, /done и т.д.) ...
# Пока давай убедимся, что этот код работает.


# --- Запуск ---
if __name__ == '__main__':
    print("Инициализирую базу данных...")
    init_db()
    print("База данных готова.")
    
    # Этот блок выполняется только когда мы запускаем бота на Render
    if 'RENDER' in os.environ:
        print("Запускаю бота в режиме вебхука...")
        WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')
        if WEBHOOK_URL:
            bot.remove_webhook()
            bot.set_webhook(url=WEBHOOK_URL)
            print(f"Вебхук установлен на {WEBHOOK_URL}")
        
        # Запускаем веб-сервер Flask
        app.run(host='0.0.0.0', port=PORT)
    else:
        # Этот блок для локального запуска на твоем компьютере для отладки
        print("Запускаю бота в режиме polling (для локальной разработки)...")
        bot.remove_webhook()
        bot.polling(none_stop=True)
