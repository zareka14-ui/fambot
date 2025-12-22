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

TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID", 0))
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- ФОНОВЫЕ ПРОВЕРКИ ---
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
            await bot.send_message(TARGET_CHAT_ID, f"🥳 <b>У НАС ПРАЗДНИК!</b>\n\nСегодня день рождения отмечает: <b>{r['name']}</b> ({r['category']})! 🎉")
        await conn.close()
    except Exception as e:
        logging.error(f"BD check error: {e}")

async def check_future_capsules(bot: Bot):
    if TARGET_CHAT_ID == 0: return
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch('SELECT id, text FROM future_messages WHERE release_date <= CURRENT_DATE')
        for row in rows:
            await bot.send_message(TARGET_CHAT_ID, f"🔔 <b>КАПСУЛА ВРЕМЕНИ!</b> 📩\n\n{row['text']}")
            await conn.execute('DELETE FROM future_messages WHERE id = $1', row['id'])
        await conn.close()
    except Exception as e:
        logging.error(f"Capsule error: {e}")

async def morning_tasks(bot: Bot):
    if TARGET_CHAT_ID != 0:
        await send_motivation_to_chat(bot, TARGET_CHAT_ID)
        await check_birthdays(bot)
        await check_future_capsules(bot)

# --- KEEP ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "OK"
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- MAIN ---
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
    await dp.start_polling(bot)

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
