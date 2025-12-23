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

# Используем быструю и стабильную модель SDXL-Lightning
HF_MODEL_URL = "https://api-inference.huggingface.co/models/ByteDance/SDXL-Lightning"

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# --- ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ ---
async def init_db():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS reputation (user_id BIGINT PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS shopping_list (id SERIAL PRIMARY KEY, item TEXT);
        CREATE TABLE IF NOT EXISTS birthdays (id SERIAL PRIMARY KEY, name TEXT, birth_date DATE);
    ''')
    await conn.close()

# --- ИИ ГЕНЕРАЦИЯ (Hugging Face) ---
async def query_hugging_face(prompt: str):
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(HF_MODEL_URL, headers=headers, json=payload, timeout=40) as resp:
                if resp.status == 200:
                    return await resp.read()
                elif resp.status == 503:
                    return "loading"
                elif resp.status == 401:
                    return "auth_error"
                else:
                    logging.error(f"HF Error: {resp.status}")
                    return None
        except Exception as e:
            logging.error(f"HF Request error: {e}")
            return None

@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer("Напиши описание. Пример: <code>/gen новогодний кот</code>")
    
    if not HF_TOKEN:
        return await message.answer("❌ Ошибка: В настройках Render не добавлен HF_TOKEN")

    msg = await message.answer("🎨 Рисую через SDXL-Lightning...")
    
    # Добавки для качества
    enhanced_prompt = f"{prompt}, high quality, detailed, masterpiece"
    result = await query_hugging_face(enhanced_prompt)

    if result == "loading":
        await msg.edit_text("⏳ Нейросеть просыпается на серверах Hugging Face... Повтори через 30-60 секунд.")
    elif result == "auth_error":
        await msg.edit_text("❌ Ошибка авторизации! Проверь правильность HF_TOKEN в Render.")
    elif result:
        try:
            await message.answer_photo(
                photo=BufferedInputFile(result, filename="ai_gen.jpg"),
                caption=f"✨ Результат: <i>{prompt}</i>"
            )
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ Ошибка отправки фото: {e}")
    else:
        await msg.edit_text("❌ Сервер Hugging Face временно недоступен или перегружен.")

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
    if not rows: return await message.answer("🏆 Рейтинг пока пуст.")
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

# --- ПРАЗДНИКИ ---
@base_router.message(Command("all_bd"))
async def list_birthdays(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, birth_date FROM birthdays ORDER BY EXTRACT(MONTH FROM birth_date), EXTRACT(DAY FROM birth_date)')
    await conn.close()
    if not rows: return await message.answer("📅 Календарь пуст.")
    res = "<b>📅 Дни рождения:</b>\n" + "\n".join([f"• {r['birth_date'].strftime('%d.%m')} — {r['name']}" for r in rows])
    await message.answer(res)

# --- БАЗОВЫЕ КОМАНДЫ ---
@base_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("🏠 Домовой на связи!\n\n/gen — Рисовать\n/buy — Покупки\n/rating — Рейтинг\n/all_bd — Праздники")

async def send_motivation_to_chat(bot: Bot, chat_id: int):
    url = f"https://picsum.photos/800/600?nature&sig={random.randint(1,999)}"
    try:
        await bot.send_photo(chat_id, url, caption="<b>Доброе утро! ✨</b>")
    except:
        await bot.send_message(chat_id, "<b>Доброе утро! ✨</b>")
