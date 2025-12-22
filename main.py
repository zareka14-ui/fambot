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

# --- СПИСОК АФОРИЗМОВ ---
family_quotes = [
    "Семья — это не главное. Семья — это всё. (Майкл Джей Фокс)",
    "Счастлив тот, кто счастлив у себя дома. (Лев Толстой)",
    "Семья — это компас, который ведет нас по жизни.",
    "Семья — это маленький мир, созданный любовью.",
    "Самое главное в жизни — это семья.",
    "Дом — это место, где всегда рады твоему возвращению.",
    "Семья — это единство души в разных телах.",
    "Всё начинается с семьи."
]

# --- ФУНКЦИЯ РАССЫЛКИ С КАРТИНКОЙ ---
async def send_daily_motivation(bot: Bot):
    chat_id = 117535475  # Ваш ID чата
    random_quote = random.choice(family_quotes)
    
    # Описание для генерации картинки (промпт)
    prompt = "Уютный загородный дом, теплая семейная атмосфера, утро, солнечные лучи сквозь окно, стиль цифровой живописи, высокое качество."

    try:
        # Отправляем фото по промпту (генерация) и подписываем афоризмом
        await bot.send_photo(
            chat_id=chat_id,
            photo=prompt, 
            caption=f"<b>Доброе утро, любимая семья! ☀️</b>\n\n<i>{random_quote}</i>"
        )
        logging.info("Daily motivation with image sent successfully")
    except Exception as e:
        logging.error(f"Failed to send motivation: {e}")

# --- KEEP ALIVE СЕРВЕР ---
app = Flask('')

@app.route('/')
def home():
    return "Бот Домовой в сети!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- ОСНОВНОЙ ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Инициализация БД
    await init_db()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(base_router)

    # Настройка планировщика (9:00 по МСК)
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_daily_motivation, "cron", hour=9, minute=0, args=[bot], misfire_grace_time=60)
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
