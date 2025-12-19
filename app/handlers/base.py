import os
import random
import asyncio
import asyncpg
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Функция подключения к БД ---
async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# --- Инициализация таблиц (вызывается при старте) ---
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

# --- 1. СИСТЕМА РЕПУТАЦИИ ---
@base_router.message(lambda message: message.text in ["+", "++", "спасибо", "Спасибо", "👍"])
async def add_reputation(message: Message):
    if not message.reply_to_message:
        return

    from_user = message.from_user
    target_user = message.reply_to_message.from_user

    if target_user.is_bot:
        return
    if from_user.id == target_user.id:
        await message.answer("Самому себе репутацию повышать нельзя! 😉")
        return

    conn = await get_db_connection()
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) 
        VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE 
        SET score = reputation.score + 1, name = $2
    ''', target_user.id, target_user.first_name)
    
    row = await conn.fetchrow('SELECT score FROM reputation WHERE user_id = $1', target_user.id)
    await conn.close()
    
    await message.answer(f"Уровень добра повышен! 📈\n<b>{target_user.first_name}</b> (+1) — итого: {row['score']}")

@base_router.message(Command("rating"))
async def show_rating(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 10')
    await conn.close()

    if not rows:
        await message.answer("Рейтинг пока пуст. Пора делать добрые дела! ✨")
        return

    res = "<b>🏆 Рейтинг полезности семьи:</b>\n\n"
    icons = ["🥇", "🥈", "🥉", "👤"]
    for i, row in enumerate(rows):
        icon = icons[i] if i < 3 else icons[3]
        res += f"{icon} {row['name']}: {row['score']}\n"
    await message.answer(res)

# --- 2. СПИСОК ПОКУПОК ---
@base_router.message(Command("купить"))
async def add_to_shopping(message: Message):
    item = message.text.replace("/купить", "").strip()
    if not item:
        await message.answer("Пример: <code>/купить хлеб</code>")
        return

    conn = await get_db_connection()
    await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
    await conn.close()
    await message.answer(f"✅ Добавил <b>{item}</b> в список.")

@base_router.message(Command("список"))
async def show_shopping(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()

    if not rows:
        await message.answer("Список покупок пуст! 🛒")
        return

    items = "\n".join([f"{i}. {row['item']}" for i, row in enumerate(rows, 1)])
    await message.answer(f"<b>🛒 Нужно купить:</b>\n\n{items}")

@base_router.message(Command("купил"))
async def clear_shopping(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список очищен! Кто-то молодец!")

# --- 3. АРХИВ ЦИТАТ ---
@base_router.message(Command("цитата"))
async def save_quote(message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.answer("Ответьте командой /цитата на чье-то текстовое сообщение.")
        return

    text = message.reply_to_message.text
    author = message.reply_to_message.from_user.first_name
    
    conn = await get_db_connection()
    await conn.execute('INSERT INTO quotes (text, author) VALUES ($1, $2)', text, author)
    await conn.close()
    await message.answer("✅ Цитата сохранена в архив!")

@base_router.message(Command("фраза"))
async def get_quote(message: Message):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT text, author FROM quotes ORDER BY RANDOM() LIMIT 1')
    await conn.close()

    if not row:
        await message.answer("Архив цитат пуст. Сохраните что-нибудь веселое!")
    else:
        await message.answer(f"📜 📜 📜\n\n«{row['text']}»\n(с) <b>{row['author']}</b>")

# --- 4. РАЗВЛЕЧЕНИЯ И НАПОМИНАЛКИ ---
@base_router.message(Command("dice"))
async def play_dice(message: Message):
    await message.answer_dice(emoji="🎲")

@base_router.message(Command("напомни"))
async def set_reminder(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Формат: <code>/напомни 10 текст</code>")
        return
    
    try:
        minutes = int(args[1])
        msg = args[2]
        await message.answer(f"Ок! Напомню через {minutes} мин.")
        await asyncio.sleep(minutes * 60)
        await message.reply(f"🔔 <b>НАПОМИНАНИЕ:</b>\n{msg}")
    except:
        await message.answer("Ошибка в формате времени.")
