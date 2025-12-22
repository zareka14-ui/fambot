import os
import random
import asyncio
import asyncpg
from aiogram import Router, types, F
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
        CREATE TABLE IF NOT EXISTS future_messages (id SERIAL PRIMARY KEY, chat_id BIGINT, text TEXT, release_date DATE);
    ''')
    await conn.close()

# --- ВСПОМОГАТЕЛЬНАЯ ЛОГИКА ---
async def get_random_family_member(message: Message):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT name FROM reputation ORDER BY RANDOM() LIMIT 1')
    await conn.close()
    return row['name'] if row else message.from_user.first_name

# --- ОСНОВНЫЕ КОМАНДЫ ---

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", web_app=WebAppInfo(url="https://prizes.gamee.com/"))],
        [
            InlineKeyboardButton(text="📜 Справка", callback_data="help_data"),
            InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_data")
        ]
    ])
    await message.answer(f"<b>Привет, {message.from_user.first_name}! 👋</b>\nЯ Домовой. Напиши /help, чтобы увидеть, что я умею.", reply_markup=keyboard)

@base_router.message(Command("help"))
async def help_command(message: Message):
    text = (
        "<b>🏠 Команды Домового:</b>\n\n"
        "🧹 <b>Быт:</b>\n"
        "/dishes - кто моет посуду\n"
        "/trash - кто выносит мусор\n"
        "/buy [текст] - добавить в список покупок\n"
        "/list - что купить\n\n"
        "🎭 <b>Развлечения:</b>\n"
        "/game - правда или действие\n"
        "/dinner_idea - что приготовить\n"
        "/future [текст] - письмо в будущее (на 1 год)\n\n"
        "📈 <b>Другое:</b>\n"
        "/rating - рейтинг семьи\n"
        "/id - узнать ID чата"
    )
    await message.answer(text)

# --- РАНДОМАЙЗЕР ОБЯЗАННОСТЕЙ ---
@base_router.message(Command("dishes", "trash"))
async def task_randomizer(message: Message):
    name = await get_random_family_member(message)
    if "dishes" in message.text:
        await message.answer(f"🧼 Сегодня посуду моет <b>{name}</b>! Без споров!")
    else:
        await message.answer(f"🗑 Жребий пал на <b>{name}</b>. Пора вынести мусор!")

# --- ИДЕЯ ДЛЯ УЖИНА ---
@base_router.message(Command("dinner_idea"))
async def dinner_idea(message: Message):
    recipes = [
        "Карбонара 🍝", "Домашние пельмени 🥟", "Курица с овощами 🍗", 
        "Стейки из лосося 🐟", "Пицца Маргарита 🍕", "Греческий салат 🥗"
    ]
    await message.answer(f"🍴 Как насчет приготовить: <b>{random.choice(recipes)}</b>?")

# --- ПРАВДА ИЛИ ДЕЙСТВИЕ ---
@base_router.message(Command("game"))
async def truth_or_dare(message: Message):
    tasks = [
        "Расскажи самый смешной случай за неделю. 😂",
        "Сделай комплимент человеку справа. ❤️",
        "Изобрази любимого киногероя без слов. 🎭",
        "Спой припев любимой песни. 🎤"
    ]
    await message.answer(f"🎲 Задание: <b>{random.choice(tasks)}</b>")

# --- КАПСУЛА ВРЕМЕНИ ---
@base_router.message(Command("future"))
async def capsule_time(message: Message):
    text_to_save = message.text.replace("/future", "").strip()
    if not text_to_save:
        return await message.answer("Напиши сообщение после команды, например: <i>/future Мы купили новую машину!</i>")
    
    conn = await get_db_connection()
    # Сохраняем дату через 365 дней
    await conn.execute(
        'INSERT INTO future_messages (chat_id, text, release_date) VALUES ($1, $2, CURRENT_DATE + INTERVAL \'1 year\')',
        message.chat.id, text_to_save
    )
    await conn.close()
    await message.answer("📩 Сообщение запечатано в капсулу времени! Я напомню о нем ровно через год.")

# --- РЕЙТИНГ И CALLBACKS ---
@base_router.callback_query(F.data == "help_data")
async def cb_help(callback: types.CallbackQuery):
    await help_command(callback.message)
    await callback.answer()

@base_router.callback_query(F.data == "rating_data")
async def cb_rating(callback: types.CallbackQuery):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 5')
    await conn.close()
    res = "<b>🏆 Топ семьи:</b>\n" + "\n".join([f"{r['name']}: {r['score']}" for r in rows]) if rows else "Рейтинг пуст."
    await callback.message.answer(res)
    await callback.answer()

# --- ПОКУПКИ (ОСТАВЛЯЕМ) ---
@base_router.message(Command("buy"))
async def add_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if item:
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
    text = "<b>🛒 Купить:</b>\n" + "\n".join([f"• {r['item']}" for r in rows])
    await message.answer(text)
