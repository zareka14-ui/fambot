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

TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID", 0))

async def morning_tasks(bot: Bot):
    if TARGET_CHAT_ID != 0:
        await send_motivation_to_chat(bot, TARGET_CHAT_ID)

app = Flask('')
@app.route('/')
def home(): return "OK"
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    await init_db()
    
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(base_router)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(morning_tasks, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
