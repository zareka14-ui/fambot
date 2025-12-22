import os
import asyncio
import logging
import sys
import asyncpg
from datetime import datetime
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import config
from app.handlers.base import base_router, init_db, send_motivation_to_chat

# Конфигурация
TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID", 0))
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- ЗАДАЧИ ПЛАНИРОВЩИКА ---
async def check_birthdays(bot: Bot):
    if TARGET_CHAT_ID == 0: return
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        today = datetime.now()
        rows = await conn.fetch(
            "SELECT name, category FROM birthdays WHERE EXTRACT(DAY FROM birth_date) = $1 AND EXTRACT(MONTH FROM birth_date) = $2",
            today.day, today.month
        )
        for r in rows:
            await bot.send_message(TARGET_CHAT_ID, f"🥳 <b>СЕГОДНЯ ПРАЗДНИК!</b>\n\nС днем рождения, <b>{r['name']}</b> ({r['category']})! 🎉")
        await conn.close()
    except Exception as e:
        logging.error(f"Error checking birthdays: {e}")

async def morning_tasks(bot: Bot):
    if TARGET_CHAT_ID != 0:
        await send_motivation_to_chat(bot, TARGET_CHAT_ID)
        await check_birthdays(bot)

# --- FLASK KEEP ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "OK"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    await init_db()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(base_router)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(morning_tasks, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()

    # Важно: сброс вебхука для чистого старта
    await bot.delete_webhook(drop_pending_updates=True)
    
    logging.info("Bot is starting polling...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
