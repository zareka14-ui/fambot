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

# Импортируем настройки и роутеры
from config.settings import config
from app.handlers.base import base_router, init_db

# --- СПИСОК АФОРИЗМОВ ДЛЯ РАССЫЛКИ ---
family_quotes = [
    "Семья — это не главное. Семья — это всё. (Майкл Джей Фокс)",
    "Счастлив тот, кто счастлив у себя дома. (Лев Толстой)",
    "Семья — это компас, который ведет нас по жизни.",
    "Семья — это маленький мир, созданный любовью.",
    "Дом — это место, где всегда рады твоему возвращению.",
    "Семья — это школа любви.",
    "Всё начинается с семьи.",
    "Семья — это один из шедевров природы. (Джордж Сантаяна)",
    "Семья — это самое теплое место на Земле."
]

# --- ЛОГИКА ОТПРАВКИ МОТИВАЦИИ (РАССЫЛКА) ---
async def send_motivation_logic(bot: Bot, chat_id: int):
    random_quote = random.choice(family_quotes)
    
    # Промпт для генерации уютной картинки
    prompt = (
        "Cozy family home interior, warm sunlight through the window, "
        "morning atmosphere, breakfast on the table, digital art style, high quality"
    )

    try:
        # Пытаемся отправить сгенерированное фото
        await bot.send_photo(
            chat_id=chat_id,
            photo=prompt, 
            caption=f"<b>Доброе утро, любимая семья! ☀️</b>\n\n<i>{random_quote}</i>"
        )
        logging.info(f"Motivation sent to {chat_id}")
    except Exception as e:
        logging.error(f"Failed to send photo motivation: {e}")
        # Если генерация фото не удалась, отправляем просто текст
        try:
            await bot.send_message(chat_id, f"<b>Доброе утро! ☀️</b>\n\n{random_quote}")
        except Exception as err:
            logging.error(f"Failed to send even text: {err}")

# Функция-обертка для планировщика
async def scheduled_job(bot: Bot):
    target_chat = int(os.environ.get("TARGET_CHAT_ID", 117535475))
    await send_motivation_logic(bot, target_chat)

# --- KEEP ALIVE (ДЛЯ RENDER) ---
app = Flask('')

@app.route('/')
def home():
    return "Бот Домовой активен и работает!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА ---
async def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    
    # 1. Инициализация базы данных
    await init_db()

    # 2. Инициализация бота
    bot = Bot(
        token=config.bot_token, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # 3. Подключаем обработчики из base.py
    dp.include_router(base_router)

    # 4. Настройка планировщика (9:00 по Москве)
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        scheduled_job, 
        "cron", 
        hour=9, 
        minute=0, 
        args=[bot], 
        misfire_grace_time=60
    )
    scheduler.start()
    logging.info("Scheduler started for 09:00 MSK")

    # 5. Очистка вебхуков (важно для устранения Conflict)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # 6. Запуск поллинга
    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке
    Thread(target=run_flask, daemon=True).start()
    
    # Запускаем основной цикл бота
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot execution stopped")
