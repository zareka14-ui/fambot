import os
import random
import asyncio
import logging
import sys
from flask import Flask
from threading import Thread

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Импорты из ваших модулей
from config.settings import config
from app.handlers.base import base_router, init_db

# --- ФУНКЦИЯ РАССЫЛКИ ---
async def send_daily_motivation(bot: Bot):
    # Ваш ID чата
    chat_id = 117535475 
    
    quotes = [
        "Семья — это не главное. Семья — это всё. ❤️",
        "Хороший день начинается с улыбки и чашки чая! 👋",
        "Не забудьте сегодня сказать друг другу 'спасибо'! ✨",
        "Семья — это там, где тебя всегда ждут. Дом — это там, где тебя любят."
    ]
    
    try:
        await bot.send_message(chat_id, f"<b>Доброе утро! ☀️</b>\n\n{random.choice(quotes)}")
        logging.info(f"Daily motivation sent to {chat_id}")
    except Exception as e:
        logging.error(f"Failed to send daily message: {e}")

# --- ВЕБ-СЕРВЕР (KEEP ALIVE) ДЛЯ RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run():
    # Render назначает порт динамически
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- ОСНОВНАЯ ЛОГИКА БОТА ---
async def main():
    # Настройка логирования в стандартный вывод Render
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )

    # 1. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
    try:
        await init_db()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        # Не останавливаем бота, если БД временно недоступна, 
        # но логируем ошибку
    
    # 2. ИНИЦИАЛИЗАЦИЯ БОТА И ДИСПЕТЧЕРА
    bot = Bot(
        token=config.bot_token, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    dp.include_router(base_router)

    # 3. НАСТРОЙКА ПЛАНИРОВЩИКА
    # Теперь он создается здесь, чтобы иметь доступ к объекту bot
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # Запуск каждый день в 9:00 утра
    scheduler.add_job(send_daily_motivation, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()
    logging.info("Scheduler started for 09:00 MSK.")

    logging.info("Starting bot on Render...")
    
    # Очищаем очередь обновлений, чтобы бот не спамил старыми сообщениями при запуске
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Polling error: {e}")
    finally:
        await bot.session.close()

if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке
    keep_alive()
    
    # Запускаем основной цикл бота
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped by user.")
