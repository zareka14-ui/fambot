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

from config.settings import config
from app.handlers.base import base_router, init_db

# --- РАССЫЛКА ---
async def send_daily_motivation(bot: Bot):
    chat_id = 117535475  # Ваш ID
    quotes = ["Семья — это всё. ❤️", "Хорошего дня! 👋", "Не забудьте про /list! ✨"]
    try:
        await bot.send_message(chat_id, f"<b>Доброе утро! ☀️</b>\n\n{random.choice(quotes)}")
        logging.info("Motivation message sent successfully")
    except Exception as e:
        logging.error(f"Рассылка не удалась: {e}")

# --- KEEP ALIVE ---
app = Flask('')
@app.route('/')
def home(): 
    return "Бот в сети"

def run_flask(): # Исправлено название функции
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- MAIN ---
async def main():
    logging.basicConfig(
        level=logging.INFO, 
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    
    # 1. Инициализация БД
    try:
        await init_db() 
        logging.info("Database initialized")
    except Exception as e:
        logging.error(f"DB Error: {e}")

    # 2. Инициализация бота
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(base_router)

    # 3. Настройка планировщика
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_daily_motivation, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()
    logging.info("Scheduler started")

    # 4. Запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    # Запуск Flask сервера в отдельном потоке
    Thread(target=run_flask, daemon=True).start()
    
    # Запуск asyncio цикла
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
