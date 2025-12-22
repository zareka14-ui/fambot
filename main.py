import os
import asyncio
import logging
import sys
import asyncpg
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import config
from app.handlers.base import base_router, init_db, send_motivation_to_chat

# Переменные окружения
TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID", 0))
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- ФУНКЦИЯ ПРОВЕРКИ КАПСУЛ ВРЕМЕНИ ---
async def check_future_capsules(bot: Bot):
    if TARGET_CHAT_ID == 0: return
    
    conn = await asyncpg.connect(DATABASE_URL)
    # Ищем сообщения, дата которых наступила или прошла
    rows = await conn.fetch(
        'SELECT id, text FROM future_messages WHERE release_date <= CURRENT_DATE'
    )
    
    for row in rows:
        await bot.send_message(
            TARGET_CHAT_ID, 
            f"🔔 <b>КАПСУЛА ВРЕМЕНИ ИЗ ПРОШЛОГО!</b> 📩\n\n{row['text']}\n\n<i>Это сообщение было оставлено ровно год назад.</i>"
        )
        # Удаляем, чтобы не слать повторно
        await conn.execute('DELETE FROM future_messages WHERE id = $1', row['id'])
    
    await conn.close()

# --- ПЛАНИРОВЩИК (9:00 УТРА) ---
async def morning_tasks(bot: Bot):
    # 1. Шлем мотивацию
    await send_motivation_to_chat(bot, TARGET_CHAT_ID)
    # 2. Проверяем капсулы времени
    await check_future_capsules(bot)

# Flask сервер
app = Flask('')
@app.route('/')
def home(): return "Бот в строю!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    await init_db()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(base_router)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # Запускаем все утренние дела в 09:00
    scheduler.add_job(morning_tasks, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Домовой готов к работе!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
