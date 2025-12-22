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
    except Exception as e:
        logging.error(f"Рассылка не удалась: {e}")

# --- KEEP ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "Бот в сети"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- MAIN ---
async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    await init_db() # Инициализация БД

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(base_router)

    # ПЛАНИРОВЩИК (Теперь внутри main)
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_daily_motivation, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
