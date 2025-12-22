import os
import random
import asyncio
import asyncpg
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

# --- ФУНКЦИЯ ДЛЯ МОТИВАЦИИ (Нужна для импорта в main.py) ---
async def send_motivation_to_chat(bot, chat_id: int):
    quotes = [
        "Семья — это не главное. Семья — это всё.",
        "Счастлив тот, кто счастлив у себя дома.",
        "Семья — это маленький мир, созданный любовью.",
        "Всё начинается с семьи."
    ]
    quote = random.choice(quotes)
    photo_url = "https://images.unsplash.com/photo-1511895426328-dc8714191300?q=80&w=1000"
    
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo_url,
            caption=f"<b>Мотивация для семьи 🏠</b>\n\n<i>{quote}</i>",
            parse_mode="HTML"
        )
    except Exception:
        await bot.send_message(chat_id, f"<b>Доброе утро! ☀️</b>\n\n{quote}")

# --- Работа с БД ---
async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS reputation (user_id BIGINT PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS shopping_list (id SERIAL PRIMARY KEY, item TEXT);
        CREATE TABLE IF NOT EXISTS future_messages (id SERIAL PRIMARY KEY, chat_id BIGINT, text TEXT, release_date DATE);
    ''')
    await conn.close()

# --- ВСПОМОГАТЕЛЬНАЯ ЛОГИКА ---
async def get_random_family_member(message: Message):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT name FROM reputation ORDER BY RANDOM() LIMIT 1')
    await conn.close()
    return row['name'] if row else message.from_user.first_name

# --- ОБРАБОТЧИКИ КОМАНД ---

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", web_app=WebAppInfo(url="https://prizes.gamee.com/"))],
        [
            InlineKeyboardButton(text="📜 Справка", callback_data="help_data"),
            InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_data")
        ]
    ])
    await message.answer(f"<b>Привет, {message.from_user.first_name}! 👋</b>\nЯ Домовой. Напиши /help.", reply_markup=keyboard)

@base_router.message(Command("help"))
async def help_command(message: Message):
    text = (
        "<b>🏠 Команды Домового:</b>\n\n"
        "/motivation - открытка\n"
        "/dishes - кто моет посуду\n"
        "/trash - кто выносит мусор\n"
        "/buy [текст] - в список покупок\n"
        "/list - что купить\n"
        "/future [текст] - письмо в будущее\n"
        "/poll [вопрос] - семейный совет\n"
        "/stat - статистика чата"
    )
    await message.answer(text)

@base_router.message(Command("motivation"))
async def manual_motivation(message: Message, bot: types.Bot):
    await send_motivation_to_chat(bot, message.chat.id)

@base_router.message(Command("dishes", "trash"))
async def task_randomizer(message: Message):
    name = await get_random_family_member(message)
    emoji = "🧼" if "dishes" in message.text else "🗑"
    await message.answer(f"{emoji} Сегодня ответственный: <b>{name}</b>!")

@base_router.message(Command("future"))
async def capsule_time(message: Message):
    text_to_save = message.text.replace("/future", "").strip()
    if not text_to_save:
        return await message.answer("Напиши текст после команды!")
    conn = await get_db_connection()
    await conn.execute(
        'INSERT INTO future_messages (chat_id, text, release_date) VALUES ($1, $2, CURRENT_DATE + INTERVAL \'1 year\')',
        message.chat.id, text_to_save
    )
    await conn.close()
    await message.answer("📩 Письмо запечатано на 1 год!")

@base_router.message(Command("stat"))
async def chat_stat(message: Message):
    conn = await get_db_connection()
    buys = await conn.fetchval('SELECT COUNT(*) FROM shopping_list')
    capsules = await conn.fetchval('SELECT COUNT(*) FROM future_messages')
    await conn.close()
    await message.answer(f"📊 <b>Статистика:</b>\nПокупок в списке: {buys}\nКапсул заложено: {capsules}")

@base_router.message(Command("poll"))
async def quick_poll(message: Message):
    q = message.text.replace("/poll", "").strip() or "Ну что, решаем?"
    await message.answer_poll(question=f"Совет: {q}", options=["Да", "Нет"], is_anonymous=False)

@base_router.callback_query(F.data == "help_data")
async def cb_help(c: types.CallbackQuery):
    await help_command(c.message)
    await c.answer()

@base_router.callback_query(F.data == "rating_data")
async def cb_rating(c: types.CallbackQuery):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 5')
    await conn.close()
    res = "<b>🏆 Топ:</b>\n" + "\n".join([f"{r['name']}: {r['score']}" for r in rows]) if rows else "Пусто"
    await c.message.answer(res)
    await c.answer()

@base_router.message(Command("buy"))
async def add_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if item:
        conn = await get_db_connection()
        await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
        await conn.close()
        await message.answer(f"✅ Записал: {item}")

@base_router.message(Command("list"))
async def list_buy(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    text = "<b>🛒 Список:</b>\n" + "\n".join([f"• {r['item']}" for r in rows]) if rows else "Пусто"
    await message.answer(text)

@base_router.message(Command("id"))
async def get_id(message: Message):
    await message.answer(f"ID чата: <code>{message.chat.id}</code>")
