import os
import random
import asyncio
import asyncpg
import aiohttp  # Новый импорт для API
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

# --- ФУНКЦИЯ ПОДКЛЮЧЕНИЯ К БД ---
async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# --- ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ ---
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
        CREATE TABLE IF NOT EXISTS birthdays (  -- НОВАЯ ТАБЛИЦА
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            day INTEGER NOT NULL,   -- День (1-31)
            month INTEGER NOT NULL  -- Месяц (1-12)
        );
    ''')
    await conn.close()

# --- КОМАНДЫ ПОМОЩИ И СТАРТА ---

@base_router.message(Command("id"))
async def get_chat_id(message: Message):
    await message.answer(f"ID этого чата: <code>{message.chat.id}</code>")

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    user_name = message.from_user.first_name
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
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
        f"• Напоминаю о днях рождения (/др)\n"
        f"• Играю и развлекаю (/knb)\n\n"
        f"Нажми кнопку ниже, чтобы заглянуть в игровой центр!"
    )
    
    await message.answer(welcome_text, reply_markup=keyboard)

# --- 1. СИСТЕМА РЕПУТАЦИИ --- (без изменений)
# ... (ваш код репутации остаётся)

# --- 2. СПИСОК ПОКУПОК --- (добавлено удаление)

@base_router.message(Command("купить", "buy"))
async def add_to_shopping(message: Message):
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
    rows = await conn.fetch('SELECT id, item FROM shopping_list ORDER BY id')  # Добавил id
    await conn.close()

    if not rows:
        await message.answer("Список покупок пуст! 🛒")
        return

    items = "\n".join([f"{row['id']}. {row['item']}" for row in rows])
    await message.answer(f"<b>🛒 Нужно купить:</b>\n\n{items}\n\nЧтобы удалить — /удалить <номер>")

@base_router.message(Command("купил", "clear"))
async def clear_shopping(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список очищен! Кто-то молодец!")

# НОВАЯ КОМАНДА УДАЛЕНИЯ
@base_router.message(Command("удалить", "del"))
async def delete_item(message: Message):
    try:
        item_id = int(message.text.split()[1])
        conn = await get_db_connection()
        result = await conn.execute('DELETE FROM shopping_list WHERE id = $1', item_id)
        await conn.close()
        if result == "DELETE 1":
            await message.answer(f"✅ Товар с номером {item_id} удалён!")
        else:
            await message.answer("❌ Товар не найден.")
    except:
        await message.answer("Использование: /удалить <номер из /список>")

# --- 3. АРХИВ ЦИТАТ --- (без изменений)
# ... (ваш код цитат)

# --- 4. ДНИ РОЖДЕНИЯ (НОВОЕ) ---

@base_router.message(Command("др", "birthday"))
async def add_birthday(message: Message):
    try:
        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            raise ValueError
        name_date = args[1]
        name, date_str = name_date.rsplit(maxsplit=1)
        day, month = map(int, date_str.split('.'))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError
        
        conn = await get_db_connection()
        await conn.execute('INSERT INTO birthdays (name, day, month) VALUES ($1, $2, $3)', name.capitalize(), day, month)
        await conn.close()
        await message.answer(f"🎉 Добавлен день рождения: <b>{name.capitalize()}</b> — {day:02d}.{month:02d}")
    except:
        await message.answer("Формат: /др Имя ДД.ММ\nПример: /др Мама 15.03")

# --- 5. РАЗВЛЕЧЕНИЯ И НАПОМИНАЛКИ --- (без изменений)
# ... (dice, who, knb и т.д.)

# --- ОБРАБОТЧИКИ КНОПОК --- (без изменений)

# --- ФУНКЦИИ ДЛЯ SCHEDULER (добавьте в main.py) ---

# 1. Напоминание о ДР
async def send_birthday_reminders(bot):
    from datetime import datetime
    today = datetime.now()
    current_day, current_month = today.day, today.month
    
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, day, month FROM birthdays')
    await conn.close()
    
    reminders = []
    for row in rows:
        bday_this_year = datetime(today.year, row['month'], row['day'])
        if bday_this_year < today.replace(hour=0, minute=0, second=0, microsecond=0):
            bday_this_year = datetime(today.year + 1, row['month'], row['day'])
        days_left = (bday_this_year - today).days
        
        if 0 <= days_left <= 7:
            if days_left == 0:
                reminders.append(f"🎂 <b>СЕГОДНЯ</b> ДР у <b>{row['name']}</b>! 🥳")
            elif days_left == 1:
                reminders.append(f"⚡ Завтра ДР у {row['name']}")
            else:
                reminders.append(f"📅 {row['name']} — {row['day']:02d}.{row['month']:02d} (через {days_left} дн.)")
    
    if reminders:
        chat_id = -100XXXXXXXXXX  # Замените на ваш семейный чат!
        text = "<b>🎉 Напоминание о днях рождения!</b>\n\n" + "\n".join(reminders)
        await bot.send_message(chat_id, text)

# 2. Ежедневная мотивация с фото
async def send_daily_motivation(bot):
    chat_id = -100XXXXXXXXXX  # Тот же чат
    
    # Получаем цитату из API (forismatic — русский, мотивирующие)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("http://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=ru") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    quote = data["quoteText"].strip()
                    author = data["quoteAuthor"].strip()
                    quote_text = f"{quote}\n\n— {author}" if author else quote
                else:
                    raise Exception
        except:
            quote_text = "Доброе утро, родные! Пусть день будет полон тепла и улыбок ❤️"
    
    full_text = f"<b>☀️ Доброе утро, семья! ☀️</b>\n\n{quote_text}\n\nС любовью от вашего бота 🌹"
    
    # Фото из Unsplash (семья/утро/мотивация)
    keywords = ["family morning", "good morning sun", "happy family", "morning motivation", "cozy breakfast"]
    query = random.choice(keywords)
    photo_url = f"https://source.unsplash.com/featured/800x600/?{query.replace(' ', '%20')}"
    
    await bot.send_photo(chat_id, photo_url, caption=full_text)
