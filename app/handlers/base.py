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
HF_TOKEN = os.getenv("HF_TOKEN")

# Самая стабильная и доступная модель для бесплатного API
HF_MODEL_URL = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# --- ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ (ВАЖНО ДЛЯ main.py) ---
async def init_db():
    conn = await get_db_connection()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS reputation (user_id BIGINT PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS shopping_list (id SERIAL PRIMARY KEY, item TEXT);
            CREATE TABLE IF NOT EXISTS birthdays (id SERIAL PRIMARY KEY, name TEXT, birth_date DATE);
        ''')
    finally:
        await conn.close()

# --- ИИ ГЕНЕРАЦИЯ (Hugging Face) ---
async def query_hugging_face(prompt: str):
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(HF_MODEL_URL, headers=headers, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    return await resp.read()
                elif resp.status == 503:
                    return "loading"
                else:
                    return f"error_{resp.status}"
        except Exception as e:
            logging.error(f"HF Request error: {e}")
            return f"exception_{str(e)[:20]}"

@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer("Напиши описание. Пример: <code>/gen кот в космосе</code>")
    
    if not HF_TOKEN:
        return await message.answer("❌ Ошибка: В Render не прописан HF_TOKEN")

    msg = await message.answer("🎨 Рисую через Hugging Face...")
    
    enhanced_prompt = f"{prompt}, highly detailed, masterpiece, 8k"
    result = await query_hugging_face(enhanced_prompt)

    if result == "loading":
        await msg.edit_text("⏳ Модель просыпается на сервере. Повтори через 30 секунд!")
    elif isinstance(result, str) and result.startswith("error_"):
        await msg.edit_text(f"❌ Сервер Hugging Face ответил ошибкой: {result.split('_')[1]}")
    elif result:
        try:
            await message.answer_photo(
                photo=BufferedInputFile(result, filename="gen.jpg"),
                caption=f"✨ <b>Результат:</b> {prompt}"
            )
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ Ошибка отправки фото: {e}")
    else:
        await msg.edit_text("❌ Неизвестная ошибка генерации.")

# --- РЕПУТАЦИЯ ---
@base_router.message(F.text == "+")
async def add_rep(message: Message):
    if not message.reply_to_message or message.reply_to_message.from_user.id == message.from_user.id:
        return
    conn = await get_db_connection()
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1
    ''', message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    await conn.close()
    await message.answer(f"👍 Репутация <b>{message.reply_to_message.from_user.first_name}</b> +1")

@base_router.message(Command("rating"))
async def cmd_rating(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC')
    await conn.close()
    if not rows: return await message.answer("🏆 Рейтинг пуст.")
    res = "<b>🏆 Рейтинг семьи:</b>\n" + "\n".join([f"{r['name']}: {r['score']}" for r in rows])
    await message.answer(res)

# --- СПИСОК ПОКУПОК ---
@base_router.message(Command("buy"))
async def cmd_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if item:
        conn = await get_db_connection()
        await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
        await conn.close()
        await message.answer(f"🛒 Добавлено: {item}")

@base_router.message(Command("list"))
async def cmd_list(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    if not rows: return await message.answer("🛒 Список пуст.")
    res = "<b>🛒 Нужно купить:</b>\n" + "\n".join([f"• {r['item']}" for r in rows])
    await message.answer(res)

@base_router.message(Command("clear"))
async def cmd_clear(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список очищен.")

# --- БАЗОВЫЕ КОМАНДЫ ---
@base_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("🏠 Домовой запущен!\n\n/gen — Рисовать\n/buy — Покупки\n/rating — Рейтинг")

# --- МОТИВАЦИЯ (ВАЖНО ДЛЯ main.py) ---
async def send_motivation_to_chat(bot: Bot, chat_id: int):
    url = f"https://picsum.photos/800/600?nature&sig={random.randint(1,999)}"
    try:
        await bot.send_photo(chat_id, url, caption="<b>Доброе утро! ✨</b>")
    except:
        await bot.send_message(chat_id, "<b>Доброе утро! ✨</b>")
