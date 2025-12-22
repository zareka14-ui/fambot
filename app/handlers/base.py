import os
import random
import asyncio
import asyncpg
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Работа с БД ---
async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS reputation (user_id BIGINT PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS shopping_list (id SERIAL PRIMARY KEY, item TEXT);
        CREATE TABLE IF NOT EXISTS quotes (id SERIAL PRIMARY KEY, text TEXT, author TEXT);
    ''')
    await conn.close()

# --- Логика мотивации (вынесена для общего доступа) ---
async def send_motivation_to_chat(bot, chat_id: int):
    quotes = [
        "Семья — это не главное. Семья — это всё.",
        "Счастлив тот, кто счастлив у себя дома.",
        "Семья — это маленький мир, созданный любовью.",
        "Всё начинается с семьи."
    ]
    quote = random.choice(quotes)
    # Используем качественное фото из открытого источника (Unsplash)
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

# --- Обработчики команд ---

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", web_app=WebAppInfo(url="https://prizes.gamee.com/"))],
        [
            InlineKeyboardButton(text="📜 Справка", callback_data="help_data"),
            InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_data")
        ]
    ])
    await message.answer(
        f"<b>Привет, {message.from_user.first_name}! 👋</b>\nЯ ваш семейный помощник.",
        reply_markup=keyboard
    )

@base_router.message(Command("motivation"))
async def cmd_motivation(message: Message, bot: types.Bot):
    await send_motivation_to_chat(bot, message.chat.id)

@base_router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "<b>🏠 Команды Домового:</b>\n\n"
        "/motivation - получить открытку\n"
        "/buy [товар] - добавить покупку\n"
        "/list - список покупок\n"
        "/rating - рейтинг семьи\n"
        "/id - узнать ID чата"
    )
    await message.answer(text)

@base_router.message(Command("id"))
async def get_id(message: Message):
    await message.answer(f"ID чата: <code>{message.chat.id}</code>")

# --- Кнопки (Callbacks) ---
@base_router.callback_query(F.data == "help_data")
async def process_help(callback: types.CallbackQuery):
    await cmd_help(callback.message)
    await callback.answer()

@base_router.callback_query(F.data == "rating_data")
async def process_rating(callback: types.CallbackQuery):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 5')
    await conn.close()
    if not rows:
        await callback.message.answer("Рейтинг пуст!")
    else:
        res = "<b>🏆 Топ семьи:</b>\n" + "\n".join([f"{r['name']}: {r['score']}" for r in rows])
        await callback.message.answer(res)
    await callback.answer()

# --- Покупки ---
@base_router.message(Command("buy"))
async def add_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if not item: return await message.answer("Пример: /buy молоко")
    conn = await get_db_connection()
    await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
    await conn.close()
    await message.answer(f"✅ Добавлено: {item}")

@base_router.message(Command("list"))
async def list_buy(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    if not rows: return await message.answer("Список пуст!")
    text = "<b>🛒 Нужно купить:</b>\n" + "\n".join([f"• {r['item']}" for r in rows])
    await message.answer(text)

# --- УЛУЧШЕННЫЙ РАНДОМАЙЗЕР (КТО СЕГОДНЯ) ---
@base_router.message(Command("dishes", "trash", "walk"))
async def who_is_it_special(message: Message):
    conn = await get_db_connection()
    # Выбираем случайного человека из базы репутации
    row = await conn.fetchrow('SELECT name FROM reputation ORDER BY RANDOM() LIMIT 1')
    await conn.close()
    
    name = row['name'] if row else message.from_user.first_name
    
    command = message.text.split('@')[0] # убираем имя бота если оно есть
    if "/dishes" in command:
        await message.answer(f"🧼 Сегодня посуду моет <b>{name}</b>!")
    elif "/trash" in command:
        await message.answer(f"🗑 Мусор выносит <b>{name}</b>. Без вариантов!")
    elif "/walk" in command:
        await message.answer(f"🦮 На прогулку идет <b>{name}</b>. Хорошей погоды!")

# --- СЛУЧАЙНЫЙ РЕЦЕПТ ---
@base_router.message(Command("dinner_idea"))
async def dinner_idea(message: Message):
    recipes = [
        "Pasta Carbonara: Спагетти, бекон, сыр, яйцо. 🍝",
        "Брускетты: Хлеб, томаты, чеснок, оливковое масло. 🥖",
        "Курица карри: Грудка, сливки, приправа карри, рис. 🍛",
        "Омлет по-французски: 3 яйца, сливочное масло, зелень. 🍳",
        "Салат Цезарь: Курица, салат, сухарики, соус. 🥗"
    ]
    await message.answer(f"🍴 Идея для ужина:\n<b>{random.choice(recipes)}</b>")

# --- ПРАВДА ИЛИ ДЕЙСТВИЕ ---
@base_router.message(Command("game"))
async def truth_or_dare(message: Message):
    tasks = [
        "Расскажи свой самый неловкий случай из детства. 👶",
        "Покажи последнее фото в галерее телефона. 📸",
        "Сделай комплимент каждому члену семьи. ❤️",
        "Изобрази кого-то из присутствующих без слов. 🎭",
        "Расскажи, что тебе больше всего нравится в нашей семье. 🏠"
    ]
    await message.answer(f"🎲 Задание для чата:\n<b>{random.choice(tasks)}</b>")
