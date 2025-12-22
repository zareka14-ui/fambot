import os
import random
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

# --- ЛОГИКА РЕЙТИНГА ---
async def show_rating_logic(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 10')
    await conn.close()
    if not rows:
        await message.answer("Рейтинг пока пуст. Пора делать добрые дела! ✨")
        return
    res = "<b>🏆 Топ активных членов семьи:</b>\n\n"
    for i, row in enumerate(rows, 1):
        res += f"{i}. {row['name']}: {row['score']}\n"
    await message.answer(res)

# --- КОМАНДЫ ---

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", web_app=WebAppInfo(url="https://prizes.gamee.com/"))],
        [
            InlineKeyboardButton(text="📜 Справка", callback_data="help_callback"),
            InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_callback")
        ]
    ])
    await message.answer(f"<b>Привет, {message.from_user.first_name}! 👋</b>\nЯ ваш семейный бот-помощник.", reply_markup=keyboard)

@base_router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "<b>🏠 Команды Домового:</b>\n\n"
        "🛒 <b>Покупки:</b> /buy [текст], /list, /clear\n"
        "📈 <b>Рейтинг:</b> /rating (или + в ответ человеку)\n"
        "📜 <b>Цитаты:</b> /quote (в ответ), /phrase\n"
        "🎮 <b>Игры:</b> /dice, /darts, /knb [камень/ножницы/бумага]\n"
        "👥 <b>Кто сегодня:</b> /who [действие]"
    )
    await message.answer(text)

@base_router.message(Command("id"))
async def get_id(message: Message):
    await message.answer(f"ID этого чата: <code>{message.chat.id}</code>")

# --- СИСТЕМА РЕПУТАЦИИ (ОТВЕТОМ НА СООБЩЕНИЕ) ---
@base_router.message(lambda message: message.text and message.text.lower() in ["+", "++", "спасибо", "👍"] and message.reply_to_message)
async def add_reputation(message: Message):
    target_user = message.reply_to_message.from_user
    if target_user.id == message.from_user.id:
        await message.answer("Нельзя повышать рейтинг самому себе! 😉")
        return
    
    conn = await get_db_connection()
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1, name = $2
    ''', target_user.id, target_user.first_name)
    await conn.close()
    await message.answer(f"Рейтинг пользователя <b>{target_user.first_name}</b> увеличен! 📈")

# --- СПИСОК ПОКУПОК ---
@base_router.message(Command("buy"))
async def add_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if not item: return await message.answer("Напишите: /buy Хлеб")
    conn = await get_db_connection()
    await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
    await conn.close()
    await message.answer(f"✅ Добавлено: {item}")

@base_router.message(Command("list"))
async def list_buy(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    if not rows: return await message.answer("Список пуст!")
    text = "<b>🛒 Нужно купить:</b>\n\n" + "\n".join([f"• {r['item']}" for r in rows])
    await message.answer(text)

@base_router.message(Command("clear"))
async def clear_buy(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список покупок очищен!")

# --- ИГРЫ ---
@base_router.message(Command("who"))
async def who_is_it(message: Message):
    action = message.text.replace("/who", "").strip()
    if not action: action = "сегодня дежурный"
    await message.answer(f"Я думаю, что <b>{action}</b> — это ты!") # Упрощено для примера

@base_router.message(Command("dice"))
async def dice(message: Message):
    await message.answer_dice("🎲")

# --- CALLBACKS ---
@base_router.callback_query(lambda c: c.data == "help_callback")
async def help_cb(c: types.CallbackQuery):
    await cmd_help(c.message)
    await c.answer()

@base_router.callback_query(lambda c: c.data == "rating_callback")
async def rating_cb(c: types.CallbackQuery):
    await show_rating_logic(c.message)
    await c.answer()
