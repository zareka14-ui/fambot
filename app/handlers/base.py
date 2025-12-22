import os
import random
import asyncio
import asyncpg
import logging
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

# --- СИСТЕМНЫЕ ФУНКЦИИ ---
async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    try:
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
    except Exception as e:
        logging.error(f"Database init error: {e}")

async def send_motivation_to_chat(bot, chat_id: int):
    quotes = [
        "Семья — это не главное. Семья — это всё.",
        "Счастлив тот, кто счастлив у себя дома.",
        "Семья — это маленький мир, созданный любовью."
    ]
    photo_url = "https://images.unsplash.com/photo-1511895426328-dc8714191300?q=80&w=1000"
    try:
        await bot.send_photo(chat_id, photo_url, caption=f"<b>Доброе утро, семья! ☀️</b>\n\n<i>{random.choice(quotes)}</i>")
    except Exception:
        await bot.send_message(chat_id, f"<b>Доброе утро! ☀️</b>\n\n{random.choice(quotes)}")

# --- КОМАНДЫ ---

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    # Используем обычную кнопку-ссылку вместо WebApp, так как она вызывает ошибку
    builder = [
        [InlineKeyboardButton(text="🎮 Открыть игры", url="https://prizes.gamee.com/")],
        [
            InlineKeyboardButton(text="📜 Справка", callback_data="help_data"),
            InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_data")
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=builder)
    
    try:
        await message.answer(
            f"<b>Привет, {message.from_user.first_name}! 👋</b>\nЯ твой Домовой. Помогаю по дому и не даю забыть о важном.", 
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Start command error: {e}")
        # Запасной вариант вообще без кнопок, если что-то пойдет не так
        await message.answer(f"Привет, {message.from_user.first_name}! Я в сети. Напиши /help для списка команд.")

@base_router.message(Command("help"))
async def help_command(message: Message):
    text = (
        "<b>🏠 Команды Домового:</b>\n\n"
        "🎂 <b>Дни рождения:</b>\n"
        "/add_bd [Имя] [ДД.ММ] [Кат] - добавить ДР\n"
        "/all_bd - список всех праздников\n\n"
        "🧹 <b>Быт и Покупки:</b>\n"
        "/dishes, /trash - кто сегодня крайний?\n"
        "/buy [товар], /list - список покупок\n\n"
        "🎭 <b>Развлечения:</b>\n"
        "/game - правда или действие\n"
        "/poll [вопрос] - семейный совет\n"
        "/future [текст] - письмо в будущее\n"
        "/stat - статистика чата"
    )
    await message.answer(text)

@base_router.message(Command("add_bd"))
async def add_birthday(message: Message):
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("Формат: <code>/add_bd Иван 25.10 Друг</code>")
    name, date_str = args[1], args[2]
    category = args[3] if len(args) > 3 else "Друг"
    try:
        day, month = map(int, date_str.split('.'))
        birth_date = datetime(2000, month, day).date()
        conn = await get_db_connection()
        await conn.execute('INSERT INTO birthdays (name, birth_date, category) VALUES ($1, $2, $3)', name, birth_date, category)
        await conn.close()
        await message.answer(f"✅ Записал: <b>{name}</b> ({category}) — {date_str}")
    except Exception as e:
        await message.answer("❌ Ошибка в дате! Пиши ДД.ММ (например, 10.05)")

@base_router.message(Command("all_bd"))
async def list_birthdays(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, birth_date, category FROM birthdays ORDER BY EXTRACT(MONTH FROM birth_date), EXTRACT(DAY FROM birth_date)')
    await conn.close()
    if not rows: return await message.answer("Список ДР пока пуст.")
    res = "<b>📅 Календарь праздников:</b>\n\n"
    for r in rows:
        res += f"• {r['birth_date'].strftime('%d.%m')} — <b>{r['name']}</b> ({r['category']})\n"
    await message.answer(res)

@base_router.message(Command("stat"))
async def chat_stat(message: Message):
    conn = await get_db_connection()
    bds = await conn.fetchval('SELECT COUNT(*) FROM birthdays')
    buys = await conn.fetchval('SELECT COUNT(*) FROM shopping_list')
    await conn.close()
    await message.answer(f"📊 <b>Статистика семьи:</b>\n\n🎂 Дней рождения: {bds}\n🛒 Покупок в списке: {buys}")

@base_router.message(Command("buy"))
async def add_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if item:
        conn = await get_db_connection()
        await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
        await conn.close()
        await message.answer(f"✅ Добавил в список: {item}")

@base_router.message(Command("list"))
async def list_buy(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    text = "<b>🛒 Нужно купить:</b>\n" + "\n".join([f"• {r['item']}" for r in rows]) if rows else "Список пуст!"
    await message.answer(text)

# --- CALLBACKS ---
@base_router.callback_query(F.data == "help_data")
async def cb_help(c: types.CallbackQuery):
    await help_command(c.message)
    await c.answer()

@base_router.callback_query(F.data == "rating_data")
async def cb_rating(c: types.CallbackQuery):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 5')
    await conn.close()
    res = "<b>🏆 Топ активных:</b>\n" + "\n".join([f"{r['name']}: {r['score']}" for r in rows]) if rows else "Пусто"
    await c.message.answer(res)
    await c.answer()

