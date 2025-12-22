import os
import random
import asyncio
import asyncpg
import logging
import aiohttp
from datetime import datetime
from aiogram import Router, types, F, Bot  # Corrected Import
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

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
        CREATE TABLE IF NOT EXISTS birthdays (
            id SERIAL PRIMARY KEY, 
            name TEXT NOT NULL, 
            birth_date DATE NOT NULL, 
            category TEXT DEFAULT 'Друг'
        );
    ''')
    await conn.close()

# --- MOTIVATION LOGIC ---
async def get_online_quote():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://zenquotes.io/api/random", timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return f"<i>«{data[0]['q']}»</i>\n\n— <b>{data[0]['a']}</b>"
    except Exception as e:
        logging.error(f"Quote API error: {e}")
    return "✨ <i>Счастье — это путь, а не пункт назначения.</i>"

async def send_motivation_to_chat(bot: Bot, chat_id: int):
    quote = await get_online_quote()
    photo_url = f"https://picsum.photos/800/600?random={random.randint(1, 1000)}"
    try:
        await bot.send_photo(chat_id, photo_url, caption=f"<b>Заряд бодрости! 💪</b>\n\n{quote}")
    except Exception as e:
        await bot.send_message(chat_id, f"<b>Доброе утро! ✨</b>\n\n{quote}")

@base_router.message(Command("motivation"))
async def cmd_motivation(message: Message, bot: Bot):
    await send_motivation_to_chat(bot, message.chat.id)

# --- GAMES & UTILS ---
@base_router.message(Command("dice"))
async def cmd_dice(message: Message): await message.answer_dice(emoji="🎲")

@base_router.message(Command("darts"))
async def cmd_darts(message: Message): await message.answer_dice(emoji="🎯")

@base_router.message(Command("knb"))
async def cmd_knb(message: Message):
    v = ["Камень ✊", "Ножницы ✌️", "Бумага ✋"]
    await message.answer(f"Мой выбор: <b>{random.choice(v)}</b>")

@base_router.message(Command("who"))
async def cmd_who(message: Message):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT name FROM reputation ORDER BY RANDOM() LIMIT 1')
    await conn.close()
    name = row['name'] if row else message.from_user.first_name
    await message.answer(f"🎯 Сегодня дежурный: <b>{name}</b>!")

# --- REPUTATION (+) ---
@base_router.message(F.text == "+")
async def add_rep(message: Message):
    if not message.reply_to_message: return
    if message.reply_to_message.from_user.id == message.from_user.id: return
    conn = await get_db_connection()
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1
    ''', message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    await conn.close()
    await message.answer(f"➕ Репутация <b>{message.reply_to_message.from_user.first_name}</b> +1!")

@base_router.message(Command("rating"))
async def cmd_rating(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 10')
    await conn.close()
    res = "<b>🏆 Рейтинг:</b>\n" + "\n".join([f"• {r['name']}: {r['score']}" for r in rows]) if rows else "Пусто"
    await message.answer(res)

# --- SHOPPING ---
@base_router.message(Command("buy"))
async def cmd_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if item:
        conn = await get_db_connection()
        await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
        await conn.close()
        await message.answer(f"✅ Добавлено: {item}")

@base_router.message(Command("list"))
async def cmd_list(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    res = "<b>🛒 Список:</b>\n" + "\n".join([f"• {r['item']}" for r in rows]) if rows else "Пусто"
    await message.answer(res)

@base_router.message(Command("clear"))
async def cmd_clear(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Очищено!")

# --- BIRTHDAYS ---
@base_router.message(Command("add_bd"))
async def add_bd(message: Message):
    a = message.text.split()
    if len(a) < 3: return await message.answer("Формат: /add_bd Имя ДД.ММ")
    try:
        d, m = map(int, a[2].split('.'))
        conn = await get_db_connection()
        await conn.execute('INSERT INTO birthdays (name, birth_date, category) VALUES ($1, $2, $3)', a[1], datetime(2000, m, d), a[3] if len(a)>3 else "Друг")
        await conn.close()
        await message.answer(f"🎂 Сохранил ДР: {a[1]}")
    except: await message.answer("Ошибка в дате!")

@base_router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("<b>🏠 Команды:</b>\n/motivation, /who, /rating, /buy, /list, /clear, /dice, /knb, /add_bd")
