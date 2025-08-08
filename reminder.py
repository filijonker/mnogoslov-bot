import os
import telebot
import sqlite3
from datetime import datetime
import pytz # Эта библиотека поможет нам работать с часовыми поясами

print("🚀 Reminder script started!")

# --- Настройки (берем из тех же переменных окружения) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
DB_NAME = 'bot_database.db'

# --- Инициализация бота ---
bot = telebot.TeleBot(BOT_TOKEN)

def send_reminders():
    """Главная функция: находит пользователей и отправляет напоминания."""
    
    # 1. Получаем текущее время по Москве (или другому часовому поясу)
    # Это важно, потому что сервер Render работает по UTC (Гринвичу)
    tz = pytz.timezone('Europe/Moscow') 
    now = datetime.now(tz)
    
    # Текущий день недели (1=Пн, 2=Вт, ..., 7=Вс)
    current_day = str(now.weekday() + 1)
    # Текущее время в формате ЧЧ:ММ
    current_time = now.strftime("%H:%M")

    print(f"Current time in Moscow: {now.strftime('%Y-%m-%d %H:%M:%S')}, Day: {current_day}, Time: {current_time}")

    # 2. Подключаемся к базе и ищем, кому пора напомнить
    try:
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()

        # Выбираем всех, у кого включены напоминания и совпадает время
        cursor.execute("SELECT telegram_id, schedule_days FROM users WHERE reminders_on = 1 AND schedule_time = ?", (current_time,))
        users_to_remind = cursor.fetchall()
        conn.close()

        print(f"Found {len(users_to_remind)} users with time {current_time}")

        # 3. Проверяем день недели и отправляем сообщения
        if not users_to_remind:
            return # Если никого не нашли, просто выходим

        for user in users_to_remind:
            user_id, schedule_days = user
            
            # Проверяем, есть ли текущий день в расписании пользователя
            if schedule_days and current_day in schedule_days.split(','):
                try:
                    print(f"Sending reminder to {user_id}...")
                    message_text = "⏰ Привет! Время писать.\n\nТвоя история ждет. Не забудь отметить свой прогресс командой `/done [число]`."
                    bot.send_message(user_id, message_text)
                    print(f"Reminder sent successfully to {user_id}")
                except Exception as e:
                    # Если пользователь заблокировал бота, мы просто игнорируем ошибку
                    print(f"Could not send message to {user_id}. Error: {e}")

    except Exception as e:
        print(f"An error occurred in a reminder script: {e}")

# --- Запуск основной функции ---
if __name__ == "__main__":
    send_reminders()
    print("✅ Reminder script finished.")

