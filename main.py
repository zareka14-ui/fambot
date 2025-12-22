import os
import asyncio
import logging
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.handlers.base import base_router, get_motivation

# Настройки
TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID", 0))

async def daily_job(bot: Bot):
    if TARGET_CHAT_ID != 0:
        # Создаем временный объект сообщения для вызова функции
        class FakeMessage:
            def __init__(self, bot, chat_id):
                self.chat = type('obj', (object,), {'id': chat_id})
                self.answer_photo = bot.send_photo
                self.answer = bot.send_message
        
        await get_motivation(FakeMessage(bot, TARGET_CHAT_ID))

# Flask для Render
app = Flask('')
@app.route('/')
def home(): return "OK"

def run(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Сначала подключаем роутер!
    dp.include_router(base_router)

    # Планировщик
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(daily_job, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    Thread(target=run).start()
    asyncio.run(main())
