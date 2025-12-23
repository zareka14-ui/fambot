import os
import asyncio
import logging
from threading import Thread
from flask import Flask

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import config
from app.handlers.base import base_router, init_db, send_motivation_to_chat
from app.services.db import init_pool
from app.services.ai_image import init_ai_services

# ====== НАСТРОЙКИ ======
TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID", 0))
PORT = int(os.environ.get("PORT", 8080))

# ====== MORNING TASK ======
async def morning_tasks(bot: Bot):
    if TARGET_CHAT_ID:
        await send_motivation_to_chat(bot, TARGET_CHAT_ID)

# ====== FLASK KEEP ALIVE ======
app = Flask(__name__)

@app.route('/')
def home():
    return "Домовой онлайн!"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ====== MAIN ======
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    logging.info("🚀 Запуск Домового")

    # 🔹 База данных
    await init_pool()
    await init_db()

    # 🔹 Проверка AI сервисов
    init_ai_services()

    # 🔹 Telegram
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()
    dp.include_router(base_router)

    # 🔹 Планировщик
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(morning_tasks, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)

    logging.info("🤖 Бот запущен и слушает Telegram")
    await dp.start_polling(bot)

# ====== ENTRY POINT ======
if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
