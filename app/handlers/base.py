import os
import random
import asyncio
import asyncpg
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Функция подключения к БД ---
async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
@base_router.message(Command("id"))
async def get_chat_id(message: Message):
    await message.answer(f"ID этого чата: <code>{message.chat.id}</code>")
@base_router.message(Command("start"))
async def cmd_start(message: Message):
    user_name = message.from_user.first_name
    
    # Кнопки под сообщением
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            # Кнопка для открытия Mini App (замените URL на свой, если будет)
            InlineKeyboardButton(text="🎮 Открыть игры", web_app=WebAppInfo(url="https://prizes.gamee.com/"))
        ],
        [
            InlineKeyboardButton(text="📜 Справка", callback_data="help_callback"),
            InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_callback")
        ]
    ])
    
    welcome_text = (
        f"<b>Привет, {user_name}! 👋</b>\n\n"
        f"Я — ваш <b>Семейный Помощник</b>. Я помогаю вести списки покупок, "
        f"коплю добрые дела и храню ваши лучшие шутки.\n\n"
        f"🚀 <b>Что я умею:</b>\n"
        f"• Веду общий список покупок (/list)\n"
        f"• Считаю рейтинг полезности (/rating)\n"
        f"• Храню цитаты семьи (/phrase)\n"
        f"• Играю и развлекаю (/knb)\n\n"
        f"Нажми кнопку ниже, чтобы заглянуть в игровой центр!"
    )
    
    await message.answer(welcome_text, reply_markup=keyboard)
# --- Инициализация таблиц ---
async def init_db():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS reputation (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            score INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS shopping_list (
            id SERIAL PRIMARY KEY,
            item TEXT
        );
        CREATE TABLE IF NOT EXISTS quotes (
            id SERIAL PRIMARY KEY,
            text TEXT,
            author TEXT
        );
    ''')
    await conn.close()

# --- 1. СИСТЕМА РЕПУТАЦИИ ---
@base_router.message(lambda message: message.text in ["+", "++", "спасибо", "Спасибо", "👍"])
async def add_reputation(message: Message):
    if not message.reply_to_message or message.reply_to_message.from_user.is_bot:
        return

    from_user = message.from_user
    target_user = message.reply_to_message.from_user

    if from_user.id == target_user.id:
        await message.answer("Самому себе репутацию повышать нельзя! 😉")
        return

    conn = await get_db_connection()
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) 
        VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE 
        SET score = reputation.score + 1, name = $2
    ''', target_user.id, target_user.first_name)
    
    row = await conn.fetchrow('SELECT score FROM reputation WHERE user_id = $1', target_user.id)
    await conn.close()
    
    await message.answer(f"Уровень добра повышен! 📈\n<b>{target_user.first_name}</b> (+1) — итого: {row['score']}")

@base_router.message(Command("rating"))
async def show_rating(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 10')
    await conn.close()

    if not rows:
        await message.answer("Рейтинг пока пуст. Пора делать добрые дела! ✨")
        return

    res = "<b>🏆 Рейтинг полезности семьи:</b>\n\n"
    icons = ["🥇", "🥈", "🥉", "👤"]
    for i, row in enumerate(rows):
        icon = icons[i] if i < 3 else icons[3]
        res += f"{icon} {row['name']}: {row['score']}\n"
    await message.answer(res)

# --- 2. СПИСОК ПОКУПОК ---
@base_router.message(Command("купить", "buy"))
async def add_to_shopping(message: Message):
    # Убираем команду из текста, чтобы оставить только название товара
    item = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    
    if not item:
        await message.answer("Пример: <code>/buy молоко</code>")
        return

    conn = await get_db_connection()
    await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
    await conn.close()
    await message.answer(f"✅ Добавил <b>{item}</b> в список.")

@base_router.message(Command("список", "list"))
async def show_shopping(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()

    if not rows:
        await message.answer("Список покупок пуст! 🛒")
        return

    items = "\n".join([f"{i}. {row['item']}" for i, row in enumerate(rows, 1)])
    await message.answer(f"<b>🛒 Нужно купить:</b>\n\n{items}")

@base_router.message(Command("купил", "clear"))
async def clear_shopping(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список очищен! Кто-то молодец!")

# --- 3. АРХИВ ЦИТАТ ---
@base_router.message(Command("цитата", "quote"))
async def save_quote(message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.answer("Ответьте командой <code>/quote</code> на текстовое сообщение.")
        return

    text = message.reply_to_message.text
    author = message.reply_to_message.from_user.first_name
    
    conn = await get_db_connection()
    await conn.execute('INSERT INTO quotes (text, author) VALUES ($1, $2)', text, author)
    await conn.close()
    await message.answer("✅ Цитата сохранена в архив!")

@base_router.message(Command("фраза", "phrase"))
async def get_quote(message: Message):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT text, author FROM quotes ORDER BY RANDOM() LIMIT 1')
    await conn.close()

    if not row:
        await message.answer("Архив цитат пуст.")
    else:
        await message.answer(f"📜\n\n«{row['text']}»\n(с) <b>{row['author']}</b>")

# --- 4. РАЗВЛЕЧЕНИЯ И НАПОМИНАЛКИ ---
@base_router.message(Command("dice"))
async def play_dice(message: Message):
    await message.answer_dice(emoji="🎲")

@base_router.message(Command("darts"))
async def play_darts(message: Message):
    await message.answer_dice(emoji="🎯")

@base_router.message(Command("who"))
async def who_is_it(message: Message):
    tasks = ["идет за хлебом 🥖", "моет посуду 🍽", "выбирает фильм 🎬", "выносит мусор 🗑"]
    task = random.choice(tasks)
    await message.answer(f"Сегодня <b>{message.from_user.first_name}</b> {task}!")

@base_router.message(Command("knb", "кнб"))
async def rps_game(message: Message):
    args = message.text.split()
    choices = {"камень": "🪨", "ножницы": "✂️", "бумага": "📄"}
    if len(args) < 2:
        await message.reply("Напиши: <code>/knb камень</code>")
        return
    user_choice = args[1].lower()
    if user_choice in choices:
        bot_choice = random.choice(list(choices.keys()))
        win_map = {"камень": "ножницы", "ножницы": "бумага", "бумага": "камень"}
        if user_choice == bot_choice: res = "Ничья! 🤝"
        elif win_map[user_choice] == bot_choice: res = "Ты победил! 🎉"
        else: res = "Я победил! 😎"
        await message.reply(f"Твой: {choices[user_choice]}\nМой: {choices[bot_choice]}\n\n{res}")

@base_router.message(Command("напомни", "remind"))
async def set_reminder(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Формат: <code>/remind 10 текст</code>")
        return
    try:
        minutes, msg = int(args[1]), args[2]
        await message.answer(f"Ок! Напомню через {minutes} мин.")
        await asyncio.sleep(minutes * 60)
        await message.reply(f"🔔 <b>НАПОМИНАНИЕ:</b>\n{msg}")
    except:
        await message.answer("Ошибка в формате времени.")

@base_router.message(Command("ужин", "dinner"))
async def dinner_poll(message: Message):
    await message.answer_poll(
        question="Что на ужин? 🍕",
        options=["Пицца/Суши", "Домашнее", "В кафе", "Холодильник"],
        is_anonymous=False
    )

@base_router.message(Command("help_fun"))
async def fun_help(message: Message):
    await message.answer(
        "<b>Команды:</b>\n/buy, /list, /clear\n/quote, /phrase\n/remind, /rating\n/knb, /dice, /who"
    )


