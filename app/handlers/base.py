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

# --- ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ (Необходима для main.py) ---
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

# --- ИИ ГЕНЕРАЦИЯ (Pollinations - Самый стабильный метод) ---
async def query_ai_image(prompt: str):
    seed = random.randint(1, 999999)
    # Кодируем текст для безопасной передачи в URL
    encoded_prompt = urllib.parse.quote(prompt)
    # Модель flux — современная и качественная
    url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    logging.error(f"AI Error: {resp.status}")
                    return None
        except Exception as e:
            logging.error(f"AI Request error: {e}")
            return None

@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer("Напиши описание. Пример: <code>/gen новогодний кот</code>")

    msg = await message.answer("🎨 Рисую... Это займет около 10 секунд.")
    
    # Улучшаем промпт автоматически
    enhanced_prompt = f"{prompt}, high quality, detailed, masterpiece"
    result = await query_ai_image(enhanced_prompt)

    if result:
        try:
            await message.answer_photo(
                photo=BufferedInputFile(result, filename="gen.jpg"),
                caption=f"✨ <b>Готово!</b>\nЗапрос: <i>{prompt}</i>"
            )
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ Ошибка отправки фото: {e}")
    else:
        await msg.edit_text("❌ Сейчас нейросеть недоступна. Попробуй еще раз через минуту.")

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
    if not rows: return await message.answer("🏆 Рейтинг семьи пока пуст.")
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
        await message.answer(f"🛒 Добавлено в список: {item}")

@base_router.message(Command("list"))
async def cmd_list(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    if not rows: return await message.answer("🛒 Список покупок пуст.")
    res = "<b>🛒 Нужно купить:</b>\n" + "\n".join([f"• {r['item']}" for r in rows])
    await message.answer(res)

@base_router.message(Command("clear"))
async def cmd_clear(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список покупок очищен.")

# --- БАЗОВЫЕ КОМАНДЫ ---
@base_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("🏠 <b>Домовой на связи!</b>\n\n"
                         "🎨 /gen — нарисовать картинку\n"
                         "🛒 /buy — добавить в покупки\n"
                         "📊 /rating — рейтинг семьи\n"
                         "➕ — ответь '+' на сообщение, чтобы поднять репутацию")

# --- МОТИВАЦИЯ (Необходима для main.py) ---
async def send_motivation_to_chat(bot: Bot, chat_id: int):
    # Берем случайную красивую картинку природы
    url = f"https://picsum.photos/800/600?nature&sig={random.randint(1,999)}"
    try:
        await bot.send_photo(chat_id, url, caption="<b>Доброе утро, любимая семья! ✨</b>\nПусть день будет чудесным.")
    except:
        await bot.send_message(chat_id, "<b>Доброе утро! ✨</b>")
