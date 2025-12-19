import os
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
from app.handlers.base import send_daily_motivation, send_birthday_reminders  # Новые функции из base.py

# --- ВЕБ-СЕРВЕР (KEEP ALIVE) ---
app = Flask('')

@app.route('/')
def home():
    return "OK"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- ОСНОВНАЯ ЛОГИКА БОТА ---
async def main():
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
        return

    # 2. Инициализация Бота
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    dp.include_router(base_router)

    # 3. НАСТРОЙКА ПЛАНИРОВЩИКА
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    # Ежедневная мотивация с красивым фото и свежей цитатой — в 7:30 утра
    scheduler.add_job(
        send_daily_motivation,
        trigger="cron",
        hour=7,
        minute=30,
        args=[bot],
        id="daily_motivation",
        replace_existing=True
    )
    
    # Напоминание о днях рождения — в 8:30 утра
    scheduler.add_job(
        send_birthday_reminders,
        trigger="cron",
        hour=8,
        minute=30,
        args=[bot],
        id="birthday_reminders",
        replace_existing=True
    )
    
    scheduler.start()
    logging.info("Scheduler запущен: мотивация в 7:30, напоминания о ДР в 8:30")

    logging.info("Starting bot on Render...")
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    keep_alive()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
