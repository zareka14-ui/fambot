import os
import random
import asyncio
import asyncpg
import logging
import urllib.parse
from datetime import datetime
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
async def init_db():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS reputation (user_id BIGINT PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS shopping_list (id SERIAL PRIMARY KEY, item TEXT);
        CREATE TABLE IF NOT EXISTS birthdays (id SERIAL PRIMARY KEY, name TEXT, birth_date DATE);
    ''')
    await conn.close()
    logging.info("Database tables initialized.")

# --- МОТИВАЦИЯ (РУССКИЙ СПИСОК) ---
async def get_russian_quote():
    quotes = [
        "Семья — это не главное. Семья — это всё. 🏠",
        "Счастлив тот, кто счастлив у себя дома. ✨",
        "Успех — это сумма маленьких усилий, повторяющихся день за днем. 💪",
        "Дом — это не место, а состояние души. 🗝",
        "Семья — это маленький мир, созданный любовью. 🌍",
        "Величайшее счастье — быть уверенным, что тебя любят. ❤️"
    ]
    return random.choice(quotes)

async def send_motivation_to_chat(bot: Bot, chat_id: int):
    quote = await get_russian_quote()
    photo_url = f"https://picsum.photos/800/600?nature,house&sig={random.randint(1, 1000)}"
    try:
        await bot.send_photo(chat_id, photo_url, caption=f"<b>Заряд бодрости! ☀️</b>\n\n{quote}")
    except Exception:
        await bot.send_message(chat_id, f"<b>Доброе утро! ☀️</b>\n\n{quote}")

# --- ГЕНЕРАЦИЯ И ИИ-ОБРАБОТКА ---
@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer("Напиши описание. Пример: <code>/gen киберпанк город</code>")
    
    msg = await message.answer("🎨 Генерирую образ...")
    encoded = urllib.parse.quote(prompt)
    url = f"https://pollinations.ai/p/{encoded}?width=1024&height=1024&seed={random.randint(1, 9999)}&model=flux"
    
    try:
        await message.answer_photo(photo=url, caption=f"✨ По запросу: <i>{prompt}</i>")
        await msg.delete()
    except:
        await msg.edit_text("❌ Ошибка генерации.")

@base_router.message(F.photo)
async def handle_ai_edit(message: Message):
    if not message.caption:
        return await message.answer("Отправь фото с <b>описанием</b> (подписью), чтобы я его обработал!\nНапример: <i>'в стиле аниме'</i>")
    
    prompt = message.caption.strip()
    msg = await message.answer("🤖 ИИ переосмысляет ваше фото...")
    encoded = urllib.parse.quote(prompt)
    url = f"https://pollinations.ai/p/{encoded}?width=1024&height=1024&seed={random.randint(1, 9999)}"
    
    try:
        await message.answer_photo(photo=url, caption=f"🎨 Обработка: <i>{prompt}</i>")
        await msg.delete()
    except:
        await msg.edit_text("❌ Ошибка ИИ-обработки.")

# --- ОСНОВНЫЕ КОМАНДЫ ---
@base_router.message(Command("start"))
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 ИИ Генерация", callback_data="btn_gen_info")],
        [InlineKeyboardButton(text="✨ Мотивация", callback_data="btn_moti")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="btn_rate")]
    ])
    await message.answer(f"Привет, {message.from_user.first_name}! Я твой Домовой.\nЯ умею рисовать, мотивировать и помогать по дому.", reply_markup=kb)

@base_router.callback_query(F.data == "btn_moti")
async def cb_moti(call: types.CallbackQuery, bot: Bot):
    await send_motivation_to_chat(bot, call.message.chat.id)
    await call.answer()

@base_router.callback_query(F.data == "btn_gen_info")
async def cb_gen_info(call: types.CallbackQuery):
    await call.message.answer("Пиши <code>/gen описание</code> для картинки с нуля\nИли пришли фото с описанием для ИИ-обработки.")
    await call.answer()

@base_router.message(Command("who"))
async def cmd_who(message: Message):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT name FROM reputation ORDER BY RANDOM() LIMIT 1')
    await conn.close()
    name = row['name'] if row else "Никто (пока пусто)"
    await message.answer(f"🎯 Сегодня дежурит: <b>{name}</b>!")

@base_router.message(F.text == "+")
async def add_rep(message: Message):
    if not message.reply_to_message or message.reply_to_message.from_user.id == message.from_user.id: return
    conn = await get_db_connection()
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1
    ''', message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    await conn.close()
    await message.answer(f"➕ Репутация <b>{message.reply_to_message.from_user.first_name}</b> +1!")

@base_router.message(Command("list"))
async def cmd_list(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    res = "<b>🛒 Список покупок:</b>\n" + "\n".join([f"• {r['item']}" for r in rows]) if rows else "Список пуст."
    await message.answer(res)

@base_router.message(Command("dbtest"))
async def db_test(message: Message):
    try:
        conn = await get_db_connection()
        await conn.close()
        await message.answer("✅ База данных Render подключена!")
    except Exception as e:
        await message.answer(f"❌ Ошибка БД: {e}")
