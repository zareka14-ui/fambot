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

from config.settings import config
from app.handlers.base import base_router, init_db, send_motivation_to_chat

# Переменная для ID чата из Render
TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID", 0))

# Flask сервер
app = Flask('')
@app.route('/')
def home(): return "Бот работает"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# Планировщик
async def scheduled_motivation(bot: Bot):
    if TARGET_CHAT_ID != 0:
        await send_motivation_to_chat(bot, TARGET_CHAT_ID)

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Инициализация БД
    await init_db()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Подключаем роутеры
    dp.include_router(base_router)

    # Настройка APScheduler
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(scheduled_motivation, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()

    # Сброс старых обновлений (убирает Conflict)
    await bot.delete_webhook(drop_pending_updates=True)
    
    logging.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
