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
from app.handlers.base import base_router, init_db # Добавили init_db сюда

# --- ВЕБ-СЕРВЕР ДЛЯ ПОДДЕРЖКИ ЖИЗНИ (KEEP ALIVE) ---
app = Flask('')

@app.route('/')
def home():
    return "OK"

def run():
    # Render автоматически назначает порт через переменную PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True # Поток умрет вместе с основной программой
    t.start()

# --- ОСНОВНАЯ ЛОГИКА БОТА ---
async def main():
    # 1. Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )

    # 2. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
    # Это создаст таблицы в PostgreSQL до того, как бот начнет работу
    try:
        await init_db()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        return # Останавливаем запуск, если база не подключилась

    # 3. Инициализация Бота
    bot = Bot(
        token=config.bot_token, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # 4. Диспетчер
    dp = Dispatcher()
    
    # 5. Регистрируем роутеры
    dp.include_router(base_router)
    
    logging.info("Starting bot on Render...")
    
    # Очистка вебхуков
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    # 1. Запускаем Flask в фоне для Render
    keep_alive()
    
    # 2. Запускаем бота
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
