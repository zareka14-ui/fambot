import os
import random
import asyncio
import asyncpg
import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS reputation (user_id BIGINT PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS shopping_list (id SERIAL PRIMARY KEY, item TEXT);
        CREATE TABLE IF NOT EXISTS future_messages (id SERIAL PRIMARY KEY, chat_id BIGINT, text TEXT, release_date DATE);
        CREATE TABLE IF NOT EXISTS birthdays (id SERIAL PRIMARY KEY, name TEXT, birth_date DATE, category TEXT);
    ''')
    await conn.close()

async def send_motivation_to_chat(bot, chat_id: int):
    quotes = ["Семья — это сила!", "Дом там, где тебя ждут.", "Счастье в мелочах."]
    try:
        await bot.send_message(chat_id, f"<b>Доброе утро! ✨</b>\n\n{random.choice(quotes)}")
    except: pass

# --- КОМАНДЫ РАЗВЛЕЧЕНИЙ (DICE, DARTS, KNB) ---
@base_router.message(Command("dice"))
async def cmd_dice(message: Message):
    await message.answer_dice(emoji="🎲")

@base_router.message(Command("darts"))
async def cmd_darts(message: Message):
    await message.answer_dice(emoji="🎯")

@base_router.message(Command("knb"))
async def cmd_knb(message: Message):
    variants = ["Камень ✊", "Ножницы ✌️", "Бумага ✋"]
    await message.answer(f"Мой выбор: <b>{random.choice(variants)}</b>")

# --- КТО СЕГОДНЯ (WHO) ---
@base_router.message(Command("who"))
async def cmd_who(message: Message):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT name FROM reputation ORDER BY RANDOM() LIMIT 1')
    await conn.close()
    name = row['name'] if row else message.from_user.first_name
    await message.answer(f"🎯 Сегодня ответственный за всё: <b>{name}</b>!")

# --- РЕЙТИНГ И РЕПУТАЦИЯ ---
@base_router.message(Command("rating"))
async def cmd_rating(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 10')
    await conn.close()
    if not rows: return await message.answer("Рейтинг пока пуст.")
    res = "<b>🏆 Рейтинг полезности:</b>\n" + "\n".join([f"{r['name']}: {r['score']} ✨" for r in rows])
    await message.answer(res)

@base_router.message(F.text == "+")
async def add_rep(message: Message):
    if not message.reply_to_message: return
    if message.reply_to_message.from_user.id == message.from_user.id:
        return await message.answer("Нельзя хвалить самого себя! 😉")
    
    conn = await get_db_connection()
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1
    ''', message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    await conn.close()
    await message.answer(f"<b>{message.from_user.first_name}</b> поблагодарил(а) <b>{message.reply_to_message.from_user.first_name}</b>! (+1)")

# --- СПИСОК ПОКУПОК (BUY, LIST, CLEAR) ---
@base_router.message(Command("buy"))
async def cmd_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if not item: return await message.answer("Напиши, что купить. Пример: /buy Хлеб")
    conn = await get_db_connection()
    await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
    await conn.close()
    await message.answer(f"✅ Добавлено: {item}")

@base_router.message(Command("list"))
async def cmd_list(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    if not rows: return await message.answer("Список покупок пуст! 🛒")
    text = "<b>🛒 Нужно купить:</b>\n" + "\n".join([f"• {r['item']}" for r in rows])
    await message.answer(text)

@base_router.message(Command("clear"))
async def cmd_clear(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список покупок очищен!")

# --- НАПОМИНАНИЯ (REMIND) ---
@base_router.message(Command("remind"))
async def cmd_remind(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3: return await message.answer("Пример: /remind 10 Поставить чайник")
    try:
        minutes = int(args[1])
        text = args[2]
        await message.answer(f"⏰ Окей, напомню через {minutes} мин: {text}")
        await asyncio.sleep(minutes * 60)
        await message.reply(f"🔔 <b>НАПОМИНАНИЕ:</b>\n{text}")
    except:
        await message.answer("Ошибка! Формат: /remind [минуты] [текст]")

# --- ГОЛОСОВАНИЕ ЗА ЕДУ (DINNER) ---
@base_router.message(Command("dinner"))
async def cmd_dinner(message: Message):
    await message.answer_poll(
        question="Что будем кушать?",
        options=["Домашняя еда 🍲", "Закажем пиццу 🍕", "Суши/Роллы 🍣", "Бургеры 🍔"],
        is_anonymous=False
    )

# --- СТАРТ И ПОМОЩЬ ---
@base_router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "<b>🏠 Все команды:</b>\n\n"
        "🎮 /dice, /darts, /knb\n"
        "🎯 /who - кто дежурный\n"
        "🏆 /rating - рейтинг\n"
        "🛒 /buy, /list, /clear - покупки\n"
        "⏰ /remind [мин] [текст]\n"
        "🍲 /dinner - опрос по еде\n"
        "🎂 /add_bd, /all_bd - дни рождения"
    )

@base_router.message(Command("id"))
async def get_id(message: Message):
    await message.answer(f"Chat ID: <code>{message.chat.id}</code>")

# Оставляем новые функции (add_bd, all_bd и т.д. из прошлого кода)
# ... (код для /add_bd и /all_bd как в предыдущем сообщении) ...
