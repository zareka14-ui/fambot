import os
import random
import asyncio
import asyncpg
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Функция подключения к БД ---
async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# --- Инициализация таблиц ---
async def init_db():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS reputation (
            user_id BIGINT PRIMARY KEY, 
            name TEXT, 
            score INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS shopping_list (
            id SERIAL PRIMARY KEY, 
            item TEXT
        );
        CREATE TABLE IF NOT EXISTS quotes (
            id SERIAL PRIMARY KEY, 
            text TEXT, 
            author TEXT
        );
    ''')
    await conn.close()

# --- Вспомогательная функция для рейтинга (чтобы кнопки не ломались) ---
async def show_rating_logic(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 10')
    await conn.close()

    if not rows:
        await message.answer("Рейтинг пока пуст. Пора делать добрые дела! ✨")
        return

    res = "<b>🏆 Рейтинг полезности семьи:</b>\n\n"
    for i, row in enumerate(rows, 1):
        res += f"{i}. {row['name']}: {row['score']}\n"
    await message.answer(res)

# --- Обработчики команд ---

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

@base_router.message(Command("rating"))
async def cmd_rating(message: Message):
    await show_rating_logic(message)

# --- Обработчики кнопок (Callbacks) ---

@base_router.callback_query(lambda c: c.data == "help_callback")
async def process_help(callback: types.CallbackQuery):
    await callback.message.answer("<b>Команды:</b>\n/buy - купить\n/list - список\n/phrase - случайная цитата")
    await callback.answer()

@base_router.callback_query(lambda c: c.data == "rating_callback")
async def process_rating(callback: types.CallbackQuery):
    await show_rating_logic(callback.message)
    await callback.answer()

# --- Покупки ---

@base_router.message(Command("buy", "купить"))
async def add_to_shopping(message: Message):
    item = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    if not item:
        await message.answer("Напишите: <code>/buy хлеб</code>")
        return
    conn = await get_db_connection()
    await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
    await conn.close()
    await message.answer(f"✅ Добавлено: {item}")

@base_router.message(Command("list", "список"))
async def show_shopping(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    if not rows:
        await message.answer("Список покупок пуст!")
        return
    items = "\n".join([f"• {row['item']}" for row in rows])
    await message.answer(f"<b>🛒 Купить:</b>\n{items}")

@base_router.message(Command("clear", "купил"))
async def clear_shopping(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список очищен!")
