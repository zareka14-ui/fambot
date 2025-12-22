import os
import random
import asyncio
import asyncpg
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def show_rating_logic(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 10')
    await conn.close()
    if not rows:
        return await message.answer("Рейтинг пока пуст. ✨")
    res = "<b>🏆 Топ активных членов семьи:</b>\n\n"
    for i, row in enumerate(rows, 1):
        res += f"{i}. {row['name']}: {row['score']}\n"
    await message.answer(res)

# --- КОМАНДЫ ---

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", web_app=WebAppInfo(url="https://prizes.gamee.com/"))],
        [
            InlineKeyboardButton(text="📜 Справка", callback_data="help_callback"),
            InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_callback")
        ]
    ])
    await message.answer(f"<b>Привет, {message.from_user.first_name}! 👋</b>\nЯ ваш семейный помощник.", reply_markup=keyboard)

@base_router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "<b>🏠 Команды Домового:</b>\n\n"
        "🛒 <b>Покупки:</b> /buy [текст], /list, /clear\n"
        "📈 <b>Рейтинг:</b> /rating (или + в ответ человеку)\n"
        "📜 <b>Цитаты:</b> /quote (в ответ), /phrase\n"
        "🎮 <b>Игры:</b> /dice, /darts, /knb [камень/ножницы/бумага]\n"
        "👥 <b>Кто сегодня:</b> /who [действие]\n"
        "⏰ <b>Напомнить:</b> /remind [мин] [текст]\n"
        "🍴 <b>Ужин:</b> /dinner"
    )
    await message.answer(text)

# --- РЕПУТАЦИЯ ---
@base_router.message(F.text.lower().in_(["+", "++", "спасибо", "👍"]), F.reply_to_message)
async def add_reputation(message: Message):
    target = message.reply_to_message.from_user
    if target.id == message.from_user.id:
        return await message.answer("Нельзя хвалить самого себя! 😉")
    conn = await get_db_connection()
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1, name = $2
    ''', target.id, target.first_name)
    await conn.close()
    await message.answer(f"Рейтинг <b>{target.first_name}</b> увеличен! 📈")

@base_router.message(Command("rating"))
async def cmd_rating(message: Message):
    await show_rating_logic(message)

# --- ПОКУПКИ ---
@base_router.message(Command("buy"))
async def add_buy(message: Message):
    item = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    if not item: return await message.answer("Напишите: /buy Хлеб")
    conn = await get_db_connection()
    await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
    await conn.close()
    await message.answer(f"✅ Добавлено: {item}")

@base_router.message(Command("list"))
async def list_buy(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    if not rows: return await message.answer("Список пуст! 🛒")
    text = "<b>🛒 Купить:</b>\n" + "\n".join([f"• {r['item']}" for r in rows])
    await message.answer(text)

@base_router.message(Command("clear"))
async def clear_buy(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список покупок очищен!")

# --- ЦИТАТЫ ---
@base_router.message(Command("quote"))
async def save_quote(message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.answer("Ответьте командой на сообщение с текстом!")
    text = message.reply_to_message.text
    author = message.reply_to_message.from_user.first_name
    conn = await get_db_connection()
    await conn.execute('INSERT INTO quotes (text, author) VALUES ($1, $2)', text, author)
    await conn.close()
    await message.answer("📍 Цитата сохранена в архив!")

@base_router.message(Command("phrase"))
async def get_phrase(message: Message):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT text, author FROM quotes ORDER BY RANDOM() LIMIT 1')
    await conn.close()
    if not row: return await message.answer("Архив цитат пуст. Сохраните что-нибудь через /quote!")
    await message.answer(f"«{row['text']}» — <b>{row['author']}</b>")

# --- ИГРЫ ---
@base_router.message(Command("who"))
async def who_is_it(message: Message):
    # В группах бот не может получить список всех участников сразу, 
    # поэтому мы шутливо выбираем того, кто вызвал команду или автора реплая
    action = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "дежурный"
    await message.answer(f"Судьба говорит, что <b>{message.from_user.first_name}</b> {action}! 🎲")

@base_router.message(Command("dice"))
async def cmd_dice(message: Message):
    await message.answer_dice("🎲")

@base_router.message(Command("darts"))
async def cmd_darts(message: Message):
    await message.answer_dice("🎯")

@base_router.message(Command("knb"))
async def cmd_knb(message: Message):
    options = ["Камень 🪨", "Ножницы ✂️", "Бумага 📄"]
    bot_choice = random.choice(options)
    await message.answer(f"Мой выбор: <b>{bot_choice}</b>!")

@base_router.message(Command("dinner"))
async def cmd_dinner(message: Message):
    await message.answer_poll(
        question="Что будем на ужин? 🍴",
        options=["Домашняя еда 🍲", "Закажем пиццу 🍕", "Суши/Роллы 🍣", "Что-то легкое 🥗"],
        is_anonymous=False
    )

# --- НАПОМИНАНИЯ ---
@base_router.message(Command("remind"))
async def cmd_remind(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3: return await message.answer("Пример: /remind 5 Выключить плиту")
    minutes, text = args[1], args[2]
    if not minutes.isdigit(): return await message.answer("Укажите время цифрами (в минутах)!")
    
    await message.answer(f"⏳ Хорошо, напомню через {minutes} мин: {text}")
    await asyncio.sleep(int(minutes) * 60)
    await message.reply(f"⏰ <b>НАПОМИНАНИЕ:</b>\n{text}")

# --- CALLBACKS ---
@base_router.callback_query(F.data == "help_callback")
async def help_cb(c: types.CallbackQuery):
    await cmd_help(c.message)
    await c.answer()

@base_router.callback_query(F.data == "rating_callback")
async def rating_cb(c: types.CallbackQuery):
    await show_rating_logic(c.message)
    await c.answer()
