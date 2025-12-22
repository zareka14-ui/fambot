import os
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
    ''')
    await conn.close()

@base_router.message(Command("id"))
async def get_id(message: Message):
    await message.answer(f"ID этого чата: <code>{message.chat.id}</code>")

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", web_app=WebAppInfo(url="https://prizes.gamee.com/"))],
        [
            InlineKeyboardButton(text="📜 Справка", callback_data="help_callback"),
            InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_callback")
        ]
    ])
    await message.answer(f"<b>Привет! 👋</b> Я Домовой.", reply_markup=keyboard)

@base_router.message(Command("help"))
async def cmd_help(message: Message):
    text = "<b>Команды:</b>\n/motivation - тест открытки\n/buy - купить\n/list - список\n/rating - рейтинг"
    await message.answer(text)

@base_router.callback_query(lambda c: c.data == "help_callback")
async def help_cb(c: types.CallbackQuery):
    await cmd_help(c.message)
    await c.answer()

# --- Остальная логика (buy, list) остается как была ---
