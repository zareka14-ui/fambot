import os
import random
import asyncio
import logging
import sys
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import config
from app.handlers.base import base_router, init_db

# --- РАСШИРЕННЫЙ СПИСОК АФОРИЗМОВ ---
family_quotes = [
    "Семья — это не главное. Семья — это всё. (Майкл Джей Фокс)",
    "Счастлив тот, кто счастлив у себя дома. (Лев Толстой)",
    "Семья — это компас, который ведет нас по жизни.",
    "Семья — это маленький мир, созданный любовью.",
    "Дом — это место, где всегда рады твоему возвращению.",
    "Семья — это единство души в разных телах.",
    "Всё начинается с семьи.",
    "Семья — это школа любви. (Святой Иоанн Златоуст)",
    "Залог семейного счастья в доброте, откровенности, отзывчивости. (Эмиль Золя)",
    "Семья — это один из шедевров природы. (Джордж Сантаяна)",
    "Семья — это самое теплое место на Земле.",
    "Любовь к родителям — основа всех добродетелей. (Цицерон)",
    "Семья — это кристалл общества. (Виктор Гюго)",
    "Нет ничего важнее уз, соединяющих семью."
]

# --- ФУНКЦИЯ ОТПРАВКИ (ИСПОЛЬЗУЕТСЯ И ДЛЯ ТЕСТА, И ДЛЯ КРОНА) ---
async def send_motivation_logic(bot: Bot, chat_id: int):
    random_quote = random.choice(family_quotes)
    
    # Качественный промпт для генерации картинки
    # Мы используем ключевые слова для создания уютной атмосферы
    prompt = (
        "Cozy family home interior, warm sunlight, morning atmosphere, "
        "beautiful flowers on a wooden table, soft colors, digital art style, high resolution"
    )

    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=prompt, 
            caption=f"<b>Мотивация для семьи 🏠</b>\n\n<i>{random_quote}</i>"
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке мотивации: {e}")
        # Если картинка не сгенерировалась, отправляем просто текст
        await bot.send_message(chat_id, f"<b>Доброе утро! ☀️</b>\n\n{random_quote}")

# Функция для планировщика
async def daily_job(bot: Bot):
    await send_motivation_logic(bot, 117535475)

# --- KEEP ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "Домовой активен"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- MAIN ---
async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    await init_db()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(base_router)

    # --- КОМАНДА ДЛЯ ТЕСТА ВНУТРИ MAIN ---
    @dp.message(Command("motivation"))
    async def manual_motivation(message: Message):
        await message.answer("Генерирую утреннюю открытку... Подождите ⏳")
        await send_motivation_logic(bot, message.chat.id)

    # Планировщик
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(daily_job, "cron", hour=9, minute=0, args=[bot], misfire_grace_time=60)
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
