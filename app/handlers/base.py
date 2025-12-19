import os
import random
import asyncio
import asyncpg
import aiohttp  # Для API цитат и Unsplash фото
from datetime import datetime
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
        CREATE TABLE IF NOT EXISTS birthdays (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            day INTEGER NOT NULL,
            month INTEGER NOT NULL
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
    rows = await conn.fetch('SELECT id, item FROM shopping_list ORDER BY id')
    await conn.close()

    if not rows:
        await message.answer("Список покупок пуст! 🛒")
        return

    items = "\n".join([f"{row['id']}. {row['item']}" for row in rows])
    await message.answer(f"<b>🛒 Нужно купить:</b>\n\n{items}\n\n<i>Удалить товар: /удалить <номер></i>")

@base_router.message(Command("купил", "clear"))
async def clear_shopping(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список очищен! Кто-то молодец!")

@base_router.message(Command("удалить", "del"))
async def delete_item(message: Message):
    try:
        item_id = int(message.text.split(maxsplit=1)[1])
        conn = await get_db_connection()
        result = await conn.execute('DELETE FROM shopping_list WHERE id = $1', item_id)
        await conn.close()
        if result == "DELETE 1":
            await message.answer(f"✅ Товар с номером {item_id} удалён из списка!")
        else:
            await message.answer("❌ Товар с таким номером не найден.")
    except:
        await message.answer("Использование: /удалить <номер>\nСмотрите номера в /список")

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

# --- 4. ДНИ РОЖДЕНИЯ ---

@base_router.message(Command("др", "birthday"))
async def add_birthday(message: Message):
    try:
        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            raise ValueError
        text_part = args[1]
        name, date_str = text_part.rsplit(maxsplit=1)
        day, month = map(int, date_str.split('.'))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError
        
        conn = await get_db_connection()
        await conn.execute(
            'INSERT INTO birthdays (name, day, month) VALUES ($1, $2, $3)',
            name.strip().capitalize(), day, month
        )
        await conn.close()
        await message.answer(f"🎉 Добавлен день рождения: <b>{name.strip().capitalize()}</b> — {day:02d}.{month:02d}")
    except Exception as e:
        await message.answer("Неверный формат!\nПравильно: /др Имя ДД.ММ\nПример: /др Папа 21.12")

# --- 5. РАЗВЛЕЧЕНИЯ И НАПОМИНАЛКИ ---

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
        if user_choice == bot_choice: 
            res = "Ничья! 🤝"
        elif win_map[user_choice] == bot_choice: 
            res = "Ты победил! 🎉"
        else: 
            res = "Я победил! 😎"
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
        "<b>Команды:</b>\n"
        "/buy, /list, /clear, /удалить\n"
        "/quote, /phrase\n"
        "/др Имя ДД.ММ — добавить день рождения\n"
        "/remind, /rating\n"
        "/knb, /dice, /who"
    )

# --- ОБРАБОТЧИКИ КНОПОК ---

@base_router.callback_query(lambda c: c.data == "help_callback")
async def process_callback_help(callback_query: types.CallbackQuery):
    help_text = (
        "<b>Справка по командам:</b>\n\n"
        "🛒 /buy [товар] — добавить покупку\n"
        "🛒 /list — показать список\n"
        "🛒 /удалить [номер] — удалить товар\n"
        "📈 /rating — рейтинг полезности\n"
        "📜 /phrase — случайная цитата\n"
        "🎉 /др Имя ДД.ММ — добавить ДР\n"
        "⏰ /remind [мин] [текст] — таймер"
    )
    await callback_query.message.answer(help_text)
    await callback_query.answer()

@base_router.callback_query(lambda c: c.data == "rating_callback")
async def process_callback_rating(callback_query: types.CallbackQuery):
    await show_rating(callback_query.message)
    await callback_query.answer()

# --- ФУНКЦИИ ДЛЯ SCHEDULER (добавьте в main.py) ---

# Ежедневная мотивация с фото и цитатой
async def send_daily_motivation(bot):
    chat_id = -1001130889326  # Ваш семейный чат
    
    # Цитата из API forismatic (на русском)
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
            quote_text = "Доброе утро, родные! Пусть день будет полон тепла, улыбок и добрых моментов ❤️"
    
    full_text = f"<b>☀️ Доброе утро, любимая семья! ☀️</b>\n\n{quote_text}\n\nС любовью от вашего бота 🌹"
    
    # Красивое случайное фото (Unsplash)
    keywords = ["family morning", "good morning", "happy family", "cozy breakfast", "sunrise family"]
    query = random.choice(keywords)
    photo_url = f"https://source.unsplash.com/featured/800x600/?{query.replace(' ', '%20')}"
    
    await bot.send_photo(chat_id, photo_url, caption=full_text)

# Напоминание о днях рождения
async def send_birthday_reminders(bot):
    chat_id = -1001130889326  # Ваш семейный чат
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
                reminders.append(f"🎂 <b>СЕГОДНЯ</b> день рождения у <b>{row['name']}</b>! 🥳🎉")
            elif days_left == 1:
                reminders.append(f"⚡ Завтра день рождения у <b>{row['name']}</b>!")
            else:
                reminders.append(f"📅 {row['name']} — {row['day']:02d}.{row['month']:02d} (через {days_left} дн.)")
    
    if reminders:
        text = "<b>🎉 Ближайшие дни рождения:</b>\n\n" + "\n".join(reminders)
        await bot.send_message(chat_id, text)
