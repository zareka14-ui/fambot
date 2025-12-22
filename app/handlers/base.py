import os
import random
import asyncio
import asyncpg
import logging
import urllib.parse
from datetime import datetime
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

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
    logging.info("Database initialized.")

# --- МОТИВАЦИЯ (РУССКИЙ СПИСОК) ---
async def get_russian_quote():
    quotes = [
        "Семья — это не главное. Семья — это всё. 🏠",
        "Счастлив тот, кто счастлив у себя дома. ✨",
        "Успех — это сумма маленьких усилий, повторяющихся день за днем. 💪",
        "Семья — это маленький мир, созданный любовью. 🌍",
        "Величайшее счастье — быть уверенным, что тебя любят. ❤️",
        "Дом — это место, где тебя всегда ждут. 🗝"
    ]
    return random.choice(quotes)

async def send_motivation_to_chat(bot: Bot, chat_id: int):
    quote = await get_russian_quote()
    photo_url = f"https://picsum.photos/800/600?nature,house&sig={random.randint(1, 1000)}"
    try:
        await bot.send_photo(chat_id, photo_url, caption=f"<b>Заряд бодрости! ☀️</b>\n\n{quote}")
    except:
        await bot.send_message(chat_id, f"<b>Доброе утро! ☀️</b>\n\n{quote}")

# --- ИИ ФУНКЦИИ (ГЕНЕРАЦИЯ И EDIT) ---
@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer("Напиши описание. Пример: <code>/gen кот в скафандре</code>")
    msg = await message.answer("🎨 Генерирую...")
    url = f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}?width=1024&height=1024&seed={random.randint(1, 9999)}&model=flux"
    try:
        await message.answer_photo(photo=url, caption=f"✨ По запросу: <i>{prompt}</i>")
        await msg.delete()
    except:
        await msg.edit_text("❌ Ошибка ИИ.")

@base_router.message(F.photo)
async def handle_ai_edit(message: Message):
    if not message.caption:
        return await message.answer("Отправь фото с <b>описанием</b> (подписью), чтобы ИИ его обработал!")
    msg = await message.answer("🤖 ИИ переосмысляет фото...")
    url = f"https://pollinations.ai/p/{urllib.parse.quote(message.caption)}?width=1024&height=1024&seed={random.randint(1, 9999)}"
    try:
        await message.answer_photo(photo=url, caption=f"🎨 Обработка: <i>{message.caption}</i>")
        await msg.delete()
    except:
        await msg.edit_text("❌ Ошибка обработки.")

# --- ПРАЗДНИКИ И ДНИ РОЖДЕНИЯ ---
@base_router.message(Command("add_bd"))
async def add_birthday(message: Message):
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("Формат: <code>/add_bd Имя ДД.ММ</code>")
    try:
        day, month = map(int, args[2].split('.'))
        b_date = datetime(2000, month, day)
        conn = await get_db_connection()
        await conn.execute('INSERT INTO birthdays (name, birth_date) VALUES ($1, $2)', args[1], b_date)
        await conn.close()
        await message.answer(f"🎂 Запомнил: {args[1]} ({args[2]})")
    except:
        await message.answer("❌ Ошибка в дате (нужно ДД.ММ)")

@base_router.message(Command("all_bd"))
async def list_birthdays(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, birth_date FROM birthdays ORDER BY EXTRACT(MONTH FROM birth_date), EXTRACT(DAY FROM birth_date)')
    await conn.close()
    if not rows: return await message.answer("📅 Календарь пуст.")
    res = "<b>📅 Календарь:</b>\n" + "\n".join([f"• {r['birth_date'].strftime('%d.%m')} — {r['name']}" for r in rows])
    await message.answer(res)

# --- СЕМЕЙНЫЕ КОМАНДЫ (ПОКУПКИ, КТО, РЕЙТИНГ) ---
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
    res = "<b>🛒 Список:</b>\n" + "\n".join([f"• {r['item']}" for r in rows]) if rows else "Пусто."
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
    await conn.execute('INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1) ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1', 
                       message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    await conn.close()
    await message.answer(f"➕ Репутация {message.reply_to_message.from_user.first_name} +1")

@base_router.message(Command("rating"))
async def cmd_rating(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC')
    await conn.close()
    res = "<b>🏆 Рейтинг семьи:</b>\n" + "\n".join([f"{r['name']}: {r['score']}" for r in rows]) if rows else "Рейтинг пуст."
    await message.answer(res)

@base_router.message(Command("who"))
async def cmd_who(message: Message):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT name FROM reputation ORDER BY RANDOM() LIMIT 1')
    await conn.close()
    name = row['name'] if row else "Никто"
    await message.answer(f"🎯 Сегодня ответственный: <b>{name}</b>!")

# --- РАЗВЛЕЧЕНИЯ И УТИЛИТЫ ---
@base_router.message(Command("dinner"))
async def cmd_dinner(message: Message):
    await message.answer_poll("🥘 Что на ужин?", ["Пицца 🍕", "Домашнее 🥗", "Суши 🍣", "Бургеры 🍔"], is_anonymous=False)

@base_router.message(Command("dice"))
async def cmd_dice(message: Message): await message.answer_dice("🎲")

@base_router.message(Command("id"))
async def cmd_id(message: Message): await message.answer(f"Chat ID: <code>{message.chat.id}</code>")

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 ИИ Рисование", callback_data="btn_gen")],
        [InlineKeyboardButton(text="✨ Мотивация", callback_data="btn_moti")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="btn_rate")]
    ])
    await message.answer("🏠 Я твой Домовой! Выбирай действие:", reply_markup=kb)

@base_router.callback_query(F.data == "btn_moti")
async def cb_moti(call: types.CallbackQuery, bot: Bot):
    await send_motivation_to_chat(bot, call.message.chat.id)
    await call.answer()
