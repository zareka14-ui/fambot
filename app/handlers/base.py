import os
import random  # Исправлено: добавлен импорт
import asyncio
import asyncpg
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS reputation (user_id BIGINT PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS shopping_list (id SERIAL PRIMARY KEY, item TEXT);
        CREATE TABLE IF NOT EXISTS quotes (id SERIAL PRIMARY KEY, text TEXT, author TEXT);
    ''')
    await conn.close()

@base_router.message(Command("id"))
async def get_chat_id(message: Message):
    await message.answer(f"ID этого чата: <code>{message.chat.id}</code>")

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    user_name = message.from_user.first_name
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", web_app=WebAppInfo(url="https://prizes.gamee.com/"))],
        [
            InlineKeyboardButton(text="📜 Справка", callback_data="help_callback"),
            InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_callback")
        ]
    ])
    await message.answer(f"<b>Привет, {user_name}! 👋</b>\nЯ ваш семейный помощник.", reply_markup=keyboard)

# --- Обработчики кнопок ---
@base_router.callback_query(lambda c: c.data == "help_callback")
async def process_help(callback: types.CallbackQuery):
    await callback.message.answer("Команды: /buy (купить), /list (список), /phrase (цитата)")
    await callback.answer()

@base_router.callback_query(lambda c: c.data == "rating_callback")
async def process_rating(callback: types.CallbackQuery):
    await show_rating(callback.message)
    await callback.answer()

# --- Остальные функции (rating, add_reputation, add_to_shopping и т.д.) ---
# Оставьте их как есть в вашем текущем файле, они работают верно.
