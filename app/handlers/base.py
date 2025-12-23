import os
import random
import asyncio
import asyncpg
import logging
import urllib.parse
import aiohttp
from datetime import datetime
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# --- ИНИЦИАЛИЗАЦИЯ БД ---
async def init_db():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS reputation (user_id BIGINT PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS shopping_list (id SERIAL PRIMARY KEY, item TEXT);
        CREATE TABLE IF NOT EXISTS birthdays (id SERIAL PRIMARY KEY, name TEXT, birth_date DATE);
    ''')
    await conn.close()

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ИИ ---
async def download_image(url: str):
    """Скачивает изображение в память, чтобы избежать пустых плашек Telegram"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception as e:
        logging.error(f"Download error: {e}")
    return None

# --- ИИ ГЕНЕРАЦИЯ И ОБРАБОТКА ---
@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer("Напиши описание. Пример: <code>/gen киберпанк город</code>")
    
    msg = await message.answer("🎨 Рисую... Это займет около 10-15 секунд.")
    
    seed = random.randint(1, 999999)
    # Используем модель 'flux' для лучшего качества
    url = f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    
    image_data = await download_image(url)
    if image_data:
        await message.answer_photo(
            photo=BufferedInputFile(image_data, filename="ai_gen.jpg"),
            caption=f"✨ Результат: <i>{prompt}</i>"
        )
        await msg.delete()
    else:
        await msg.edit_text("❌ Сервис ИИ не ответил. Попробуй позже.")

@base_router.message(F.photo)
async def handle_ai_edit(message: Message):
    if not message.caption:
        return await message.answer("Пришли фото с <b>описанием</b> того, что нужно сделать (например: 'сделай в стиле аниме')")
    
    msg = await message.answer("🤖 ИИ перерисовывает фото...")
    prompt = message.caption.strip()
    seed = random.randint(1, 999999)
    url = f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    
    image_data = await download_image(url)
    if image_data:
        await message.answer_photo(
            photo=BufferedInputFile(image_data, filename="ai_edit.jpg"),
            caption=f"🎨 Обработка: <i>{prompt}</i>"
        )
        await msg.delete()
    else:
        await msg.edit_text("❌ Ошибка обработки фото.")

# --- ОСТАЛЬНЫЕ ФУНКЦИИ (ПОКУПКИ, РЕЙТИНГ, ПРАЗДНИКИ) ---
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
    res = "<b>🛒 Список:</b>\n" + "\n".join([f"• {r['item']}" for r in rows]) if rows else "Список пуст."
    await message.answer(res)

@base_router.message(Command("clear"))
async def cmd_clear(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список очищен.")

@base_router.message(F.text == "+")
async def add_rep(message: Message):
    if not message.reply_to_message or message.reply_to_message.from_user.id == message.from_user.id: return
    conn = await get_db_connection()
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1
    ''', message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    await conn.close()
    await message.answer(f"➕ Репутация {message.reply_to_message.from_user.first_name} +1")

@base_router.message(Command("all_bd"))
async def list_birthdays(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, birth_date FROM birthdays ORDER BY EXTRACT(MONTH FROM birth_date), EXTRACT(DAY FROM birth_date)')
    await conn.close()
    if not rows: return await message.answer("📅 Календарь пуст.")
    res = "<b>📅 Календарь:</b>\n" + "\n".join([f"• {r['birth_date'].strftime('%d.%m')} — {r['name']}" for r in rows])
    await message.answer(res)

async def send_motivation_to_chat(bot: Bot, chat_id: int):
    quotes = ["Семья — это всё. 🏠", "Успех — это сумма усилий. 💪", "Дом там, где тебя ждут. 🗝"]
    quote = random.choice(quotes)
    url = f"https://picsum.photos/800/600?nature&sig={random.randint(1,1000)}"
    try:
        await bot.send_photo(chat_id, url, caption=f"<b>Доброе утро!</b>\n\n{quote}")
    except:
        await bot.send_message(chat_id, f"<b>Доброе утро!</b>\n\n{quote}")
