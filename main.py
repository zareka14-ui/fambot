# main.py
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
# --- НОВЫЕ ИМПОРТЫ ДЛЯ ПРОКСИ ---
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp_socks import ProxyType, ProxyConnector 
# ---------------------------------

# Импорты из наших модулей
from config.settings import config
from app.handlers.base import base_router
from app.database import db_connect 
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp_socks import ProxyConnector

# --- КОНСТАНТА ПРОКСИ ДЛЯ PYTHONANYWHERE ---
# Для aiogram 3.x с aiohttp-socks нужно использовать ProxyConnector, 
# а не просто прокси-URL в строковом виде.
PROXY_URL = "http://proxy.server:3128"


async def main():
    # 1. Настройка логирования
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
  # 2. Инициализация Прокси-Сессии (ИЗМЕНЕННЫЙ КОД!)
    proxy_connector = ProxyConnector.from_url(PROXY_URL)
    
    # Создаем AiohttpSession, передавая connector в aiohttp_session_kwargs
    session = AiohttpSession(
        aiohttp_session_kwargs={
            "connector": proxy_connector
        }
    )
    
    # 3. Инициализация Бота с настроенной сессией
    bot = Bot(
        token=config.bot_token, 
        session=session, # <-- Передаем сессию
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # 4. Диспетчер
    dp = Dispatcher()
    
    # 5. Регистрируем роутеры
    dp.include_router(base_router)
    
    # 6. Запуск
    logging.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")