import os
import random
import asyncio
import asyncpg
import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

# --- СИСТЕМНЫЕ ФУНКЦИИ ---
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

async def send_motivation_to_chat(bot, chat_id: int):
    quotes = ["Семья — это сила!", "Счастлив тот, кто счастлив дома.", "Семья — это всё."]
    try:
        await bot.send_message(chat_id, f"<b>Доброе утро, любимая семья! ✨</b>\n\n{random.choice(quotes)}")
    except: pass

# --- ИГРЫ И РАЗВЛЕЧЕНИЯ ---
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
    await message.answer(f"🎯 Сегодня ответственный (дежурный): <b>{name}</b>!")

# --- РЕПУТАЦИЯ И РЕЙТИНГ ---
@base_router.message(Command("rating"))
async def cmd_rating(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 10')
    await conn.close()
    if not rows: return await message.answer("Рейтинг пока пуст.")
    res = "<b>🏆 Рейтинг полезности:</b>\n\n" + "\n".join([f"{r['name']}: {r['score']} ✨" for r in rows])
    await message.answer(res)

@base_router.message(F.text == "+")
async def add_rep(message: Message):
    if not message.reply_to_message: return
    if message.reply_to_message.from_user.id == message.from_user.id:
        return await message.answer("Самопохвала — это хорошо, но баллы так не заработать! 😉")
    
    conn = await get_db_connection()
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1
    ''', message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    await conn.close()
    await message.answer(f"➕ <b>{message.from_user.first_name}</b> повысил(а) репутацию <b>{message.reply_to_message.from_user.first_name}</b>!")

# --- ПОКУПКИ (BUY, LIST, CLEAR) ---
@base_router.message(Command("buy"))
async def cmd_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if not item: return await message.answer("Напиши что купить. Пример: /buy Молоко")
    conn = await get_db_connection()
    await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
    await conn.close()
    await message.answer(f"✅ Добавлено в список: {item}")

@base_router.message(Command("list"))
async def cmd_list(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    if not rows: return await message.answer("Список покупок пуст! 🛒")
    text = "<b>🛒 Список покупок:</b>\n" + "\n".join([f"• {r['item']}" for r in rows])
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
    if len(args) < 3: return await message.answer("Формат: /remind [минуты] [текст]")
    try:
        minutes = int(args[1])
        text = args[2]
        await message.answer(f"⏰ Ок! Напомню через {minutes} мин: {text}")
        await asyncio.sleep(minutes * 60)
        await message.reply(f"🔔 <b>НАПОМИНАНИЕ:</b>\n{text}")
    except:
        await message.answer("Ошибка! Минуты должны быть числом.")

# --- УЖИН / ОПРОС (DINNER) ---
@base_router.message(Command("dinner"))
async def cmd_dinner(message: Message):
    await message.answer_poll(
        question="Что будем сегодня на ужин? 🍲",
        options=["Домашняя еда 🥗", "Закажем пиццу 🍕", "Суши/Роллы 🍣", "Бургеры/Фастфуд 🍔", "Свой вариант (в чат) 💬"],
        is_anonymous=False
    )

# --- ДНИ РОЖДЕНИЯ (ADD_BD, ALL_BD) ---
@base_router.message(Command("add_bd"))
async def add_birthday(message: Message):
    args = message.text.split()
    if len(args) < 3: return await message.answer("Формат: /add_bd Имя ДД.ММ Категория")
    name, date_str = args[1], args[2]
    category = args[3] if len(args) > 3 else "Друг"
    try:
        day, month = map(int, date_str.split('.'))
        birth_date = datetime(2000, month, day).date()
        conn = await get_db_connection()
        await conn.execute('INSERT INTO birthdays (name, birth_date, category) VALUES ($1, $2, $3)', name, birth_date, category)
        await conn.close()
        await message.answer(f"🎂 Записал день рождения: <b>{name}</b> ({date_str})")
    except:
        await message.answer("❌ Ошибка в дате! Пиши ДД.ММ (например, 15.01)")

@base_router.message(Command("all_bd"))
async def list_birthdays(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, birth_date, category FROM birthdays ORDER BY EXTRACT(MONTH FROM birth_date), EXTRACT(DAY FROM birth_date)')
    await conn.close()
    if not rows: return await message.answer("Календарь пуст.")
    res = "<b>📅 Календарь событий:</b>\n\n"
    for r in rows:
        res += f"• {r['birth_date'].strftime('%d.%m')} — <b>{r['name']}</b> ({r['category']})\n"
    await message.answer(res)

# --- ПОМОЩЬ И ID ---
@base_router.message(Command("help"))
async def help_command(message: Message):
    text = (
        "<b>🏠 Домовой на связи! Команды:</b>\n\n"
        "🎮 /dice, /darts, /knb - игры\n"
        "🎯 /who - кто сегодня главный?\n"
        "🏆 /rating - топ полезности\n"
        "🛒 /buy, /list, /clear - список покупок\n"
        "⏰ /remind [мин] [текст] - таймер\n"
        "🍲 /dinner - опрос по еде\n"
        "🎂 /add_bd, /all_bd - дни рождения\n"
        "🆔 /id - узнать ID чата"
    )
    await message.answer(text)

@base_router.message(Command("id"))
async def get_id(message: Message):
    await message.answer(f"ID этого чата: <code>{message.chat.id}</code>")

# --- CALLBACKS ---
@base_router.callback_query(F.data == "help_data")
async def cb_help(c: types.CallbackQuery):
    await help_command(c.message)
    await c.answer()

@base_router.callback_query(F.data == "rating_data")
async def cb_rating(c: types.CallbackQuery):
    await cmd_rating(c.message)
    await c.answer()
