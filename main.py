import os
import asyncio
import logging
import sys
from flask import Flask
from threading import Thread

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Импорты из ваших модулей
from config.settings import config
from app.handlers.base import base_router
# from app.database import db_connect # Раскомментируйте, если используете

# --- ВЕБ-СЕРВЕР ДЛЯ ПОДДЕРЖКИ ЖИЗНИ (KEEP ALIVE) ---
app = Flask('')

@app.route('/')
def home():
    return "OK" # Минимум текста, чтобы Cron-job не ругался

def run():
    # Render автоматически назначает порт. Если его нет, используем 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- ОСНОВНАЯ ЛОГИКА БОТА ---
async def main():
    # 1. Настройка логирования (INFO достаточно, чтобы не забивать логи)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    
    # 2. Инициализация Бота
    # УБРАЛИ ПРОКСИ: На Render они не нужны и будут выдавать ошибку подключения
    bot = Bot(
        token=config.bot_token, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # 3. Диспетчер
    dp = Dispatcher()
    
    # 4. Регистрируем роутеры
    dp.include_router(base_router)
    
    # 5. Запуск
    logging.info("Starting bot on Render...")
    
    # Удаляем вебхуки, чтобы бот мог работать через long polling
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    # Запускаем Flask в фоне
    keep_alive()
    
    # Запускаем бота
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
