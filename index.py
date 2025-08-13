import os
import telebot
import sqlite3
import json
from flask import Flask, request
from telebot import types, TeleBot
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage # Хранилище состояний
from textwrap import dedent
import random

# --- Настройки ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DB_NAME = 'bot_database.db' 

# --- Инициализация (с изменениями) ---
# Создаем хранилище состояний
state_storage = StateMemoryStorage() 
# Передаем хранилище боту
bot = TeleBot(BOT_TOKEN, state_storage=state_storage) 
app = Flask(__name__)

# --- База данных (без изменений) ---
def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, goal_chars INTEGER, current_progress INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

# --- Вебхук (без изменений) ---
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

# --- НОВЫЙ СПОСОБ ОРГАНИЗАЦИИ ДИАЛОГА (FSM) ---
# 1. Описываем все состояния нашего диалога
class MyStates(StatesGroup):
    awaiting_goal = State()
    awaiting_days = State()
    awaiting_chars = State()

# 2. Обработчик /start, который НАЧИНАЕТ диалог
@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    welcome_text = "*Я — бот-помощник *Многослов*...*\n\n...Теперь введи числом, сколько знаков будет в твоей книге?"
    bot.send_message(chat_id, dedent(welcome_text), parse_mode="Markdown")
    # Устанавливаем первое состояние для пользователя
    bot.set_state(message.from_user.id, MyStates.awaiting_goal, chat_id)

# 3. Обработчики для каждого состояния
@bot.message_handler(state=MyStates.awaiting_goal)
def goal_handler(message):
    try:
        goal = int(message.text)
        # Сохраняем данные во временное хранилище FSM
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['goal_chars'] = goal
        
        bot.send_message(message.chat.id, "Отлично! А сколько дней в неделю ты планируешь писать?")
        # Переключаем на следующее состояние
        bot.set_state(message.from_user.id, MyStates.awaiting_days, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введи число.")

@bot.message_handler(state=MyStates.awaiting_days)
def days_handler(message):
    try:
        days = int(message.text)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['days_per_week'] = days

        bot.send_message(message.chat.id, "Понял-принял. Примерно сколько знаков за одну сессию?")
        bot.set_state(message.from_user.id, MyStates.awaiting_chars, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введи число (например, 7).")

@bot.message_handler(state=MyStates.awaiting_chars)
def chars_handler(message):
    chat_id = message.chat.id
    try:
        with bot.retrieve_data(message.from_user.id, chat_id) as data:
            goal = data['goal_chars']
            days = data['days_per_week']
        
        chars_per_session = int(message.text)
        chars_per_week = days * chars_per_session
        weeks_needed = goal / chars_per_week if chars_per_week > 0 else 0
        # ... (здесь твой код для get_time_string)
        time_str = f"{round(weeks_needed)} недель" # Упрощенный расчет для примера

        final_text = f"*Отлично, твой план готов!*\n...\nПри таком темпе, тебе потребуется *{time_str}*."
        bot.send_message(chat_id, dedent(final_text), parse_mode="Markdown")

        # Сохраняем в базу
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (telegram_id, goal_chars) VALUES (?, ?)", (chat_id, goal))
        conn.commit()
        conn.close()

        # Завершаем диалог, сбрасывая состояние
        bot.delete_state(message.from_user.id, chat_id)

    except (ValueError, KeyError):
        bot.send_message(chat_id, "Что-то пошло не так. Давай начнем сначала? /start")
        bot.delete_state(message.from_user.id, chat_id)

# --- Остальные команды (остаются такими же) ---
@bot.message_handler(state="*", commands=['stats', 'done', 'help', 'inspiration']) # state="*" - для работы из любого состояния
def any_state_commands(message):
    bot.delete_state(message.from_user.id, message.chat.id) # Прерываем диалог, если он был
    if message.text.startswith('/stats'):
        # ... (код stats_handler)
        pass 
    elif message.text.startswith('/done'):
        # ... (код done_handler)
        pass
    # ... и так далее

# --- Запуск (без изменений) ---
if __name__ == '__main__':
    # ...
