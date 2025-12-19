import os
import random
import asyncio
import asyncpg
import aiohttp
from datetime import datetime
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, CallbackQuery

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

# --- ПОДКЛЮЧЕНИЕ К БД ---
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
        CREATE TABLE IF NOT EXISTS knb_stats (
            user_id BIGINT PRIMARY KEY,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0
        );
    ''')
    await conn.close()

# --- КОМАНДЫ СТАРТА И ПОМОЩИ ---
@base_router.message(Command("id"))
async def get_chat_id(message: Message):
    await message.answer(f"ID этого чата: <code>{message.chat.id}</code>")

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    user_name = message.from_user.first_name
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Открыть игры", web_app=WebAppInfo(url="https://prizes.gamee.com/"))],
        [InlineKeyboardButton(text="📜 Справка", callback_data="help_callback"),
         InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_callback")]
    ])
    
    welcome_text = (
        f"<b>Привет, {user_name}! 👋</b>\n\n"
        "Я — ваш <b>Семейный Помощник</b>. Помогаю вести списки покупок, коплю добрые дела, храню тёплые моменты и развлекаю!\n\n"
        "🚀 <b>Что я умею:</b>\n"
        "• Список покупок (/list, /buy)\n"
        "• Рейтинг полезности (+, /rating)\n"
        "• Архив цитат (/phrase)\n"
        "• Дни рождения (/др)\n"
        "• Погода (/погода [город])\n"
        "• Камень-ножницы-бумага (/knb)\n\n"
        "Нажми кнопку ниже, чтобы заглянуть в игровой центр!"
    )
    
    await message.answer(welcome_text, reply_markup=keyboard)

# --- 1. РЕПУТАЦИЯ ---
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
    await message.answer(f"<b>🛒 Нужно купить:</b>\n\n{items}\n\n<i>Удалить: /удалить <номер></i>")

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
            await message.answer(f"✅ Товар с номером {item_id} удалён!")
        else:
            await message.answer("❌ Товар не найден.")
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
    await message.answer("✅ Цитата сохранена!")

@base_router.message(Command("фраза", "phrase"))
async def get_quote(message: Message):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT text, author FROM quotes ORDER BY RANDOM() LIMIT 1')
    await conn.close()

    if
    if not row:
        await message.answer("Архив цитат пуст.")
    else:
        await message.answer(f"📜\n\n«{row['text']}»\n(с) <b>{row['author']}</b>")

# --- 4. ДНИ РОЖДЕНИЯ ---
@base_router.message(Command("др", "birthday"))
async def add_birthday(message: Message):
    try:
        text_part = message.text.split(maxsplit=2)[1]
        name, date_str = text_part.rsplit(maxsplit=1)
        day, month = map(int, date_str.split('.'))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError
        
        conn = await get_db_connection()
        await conn.execute('INSERT INTO birthdays (name, day, month) VALUES ($1, $2, $3)', name.strip().capitalize(), day, month)
        await conn.close()
        await message.answer(f"🎉 Добавлен день рождения: <b>{name.strip().capitalize()}</b> — {day:02d}.{month:02d}")
    except:
        await message.answer("Неверный формат!\nПравильно: /др Имя ДД.ММ\nПример: /др Мама 15.03")

# --- 5. ПОГОДА (wttr.in — без ключа) ---
async def get_weather(city: str = "Москва") -> str:
    city_encoded = city.strip().replace(" ", "+")
    url = f"https://wttr.in/{city_encoded}?format=%l+%c+%t+%w+%h%%25+%P&lang=ru"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    parts = text.strip().split(" +")
                    if len(parts) >= 6:
                        location, condition, temp, wind, humidity, pressure = parts
                        return (
                            f"🌤️ <b>Погода в {location}:</b>\n\n"
                            f"{condition}\n"
                            f"🌡️ Температура: {temp}\n"
                            f"💨 Ветер: {wind}\n"
                            f"💧 Влажность: {humidity}\n"
                            f"🌀 Давление: {pressure}"
                        )
                    else:
                        return "🌧️ Данные погоды временно недоступны."
                else:
                    return "🌧️ Не удалось получить погоду."
        except:
            return "🌧️ Ошибка связи с сервисом погоды."

@base_router.message(Command("погода", "weather"))
async def cmd_weather(message: Message):
    args = message.text.split(maxsplit=1)
    city = args[1].strip() if len(args) > 1 else "Москва"
    weather_text = await get_weather(city)
    await message.answer(weather_text)

# --- 6. УЛУЧШЕННАЯ КНБ ---
choices_emoji = {"камень": "🪨", "ножницы": "✂️", "бумага": "📄"}
win_map = {"камень": "ножницы", "ножницы": "бумага", "бумага": "камень"}

@base_router.message(Command("knb", "кнб"))
async def cmd_knb_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🪨 Камень", callback_data="knb_камень"),
            InlineKeyboardButton(text="✂️ Ножницы", callback_data="knb_ножницы"),
            InlineKeyboardButton(text="📄 Бумага", callback_data="knb_бумага")
        ],
        [InlineKeyboardButton(text="📊 Моя стати remarkстика", callback_data="knb_my_stats")]
    ])
    
    await message.answer(
        f"<b>{message.from_user.first_name}, сыграем в Камень-Ножницы-Бумага? 🎮</b>\n\nВыбери свой ход:",
        reply_markup=keyboard
    )

@base_router.callback_query(lambda c: c.data.startswith("knb_") and c.data not in ["knb_my_stats", "knb_restart"])
async def process_knb_choice(callback: CallbackQuery):
    user_choice = callback.data.split("_")[1]
    bot_choice = random.choice(["камень", "ножницы", "бумага"])
    
    await callback.message.edit_text(
        f"<b>{callback.from_user.first_name} vs Бот</b>\n\n"
        f"Ты: {choices_emoji[user_choice]}\n"
        f"Бот: ❓\n\n<i>Бросаем...</i>"
    )
    await asyncio.sleep(1.8)
    
    if user_choice == bot_choice:
        result = "🤝 Ничья!"
        stat_field = "draws"
    elif win_map[user_choice] == bot_choice:
        result = "🎉 Ты победил!"
        stat_field = "wins"
    else:
        result = "😎 Я победил!"
        stat_field = "losses"
    
    conn = await get_db_connection()
    await conn.execute(f'''
        INSERT INTO knb_stats (user_id, {stat_field}) VALUES ($1, 1)
        ON CONFLICT (user_id) DO UPDATE SET {stat_field} = knb_stats.{stat_field} + 1
    ''', callback.from_user.id)
    row = await conn.fetchrow('SELECT wins, losses, draws FROM knb_stats WHERE user_id = $1', callback.from_user.id)
    await conn.close()
    
    total = row['wins'] + row['losses'] + row['draws']
    
    text = (
        f"<b>Раунд завершён!</b>\n\n"
        f"Ты: {choices_emoji[user_choice]} <b>{user_choice.capitalize()}</b>\n"
        f"Бот: {choices_emoji[bot_choice]} <b>{bot_choice.capitalize()}</b>\n\n"
        f"<b>{result}</b>\n\n"
        f"📊 Твоя статистика: {row['wins']}W • {row['losses']}L • {row['draws']}D (из {total})"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Ещё раз!", callback_data="knb_restart")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@base_router.callback_query(lambda c: c.data == "knb_restart")
async def knb_restart(callback: CallbackQuery):
    await cmd_knb_start(callback.message)
    await callback.answer()

@base_router.callback_query(lambda c: c.data == "knb_my_stats")
async def knb_my_stats(callback: CallbackQuery):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT wins, losses, draws FROM knb_stats WHERE user_id = $1', callback.from_user.id)
    await conn.close()
    
    if not row or (row['wins'] + row['losses'] + row['draws']) == 0:
        text = "Ты ещё не играл в КНБ со мной 😢\nНажми ниже, чтобы начать!"
    else:
        total = row['wins'] + row['losses'] + row['draws']
        winrate = round(row['wins'] / total * 100, 1)
        text = (
            f"<b>Твоя статистика в КНБ:</b>\n\n"
            f"🎉 Побед: {row['wins']}\n"
            f"😔 Поражений: {row['losses']}\n"
            f"🤝 Ничьих: {row['draws']}\n"
            f"📊 Всего: {total}\n"
            f"💪 Винрейт: {winrate}%"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть!", callback_data="knb_restart")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@base_router.message(Command("knbtop"))
async def knb_top(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('''
        SELECT user_id, wins, losses, draws 
        FROM knb_stats 
        WHERE wins + losses + draws > 0
        ORDER BY wins DESC LIMIT 10
    ''')
    await conn.close()
    
    if not rows:
        await message.answer("Пока никто не играл в КНБ 😔\nНачните: /knb")
        return
    
    text = "<b>🏆 ТОП мастеров КНБ:</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        total = row['wins'] + row['losses'] + row['draws']
        winrate = round(row['wins'] / total * 100, 1) if total > 0 else 0
        text += f"{medal} <b>User</b>: {row['wins']} побед ({winrate}%)\n"
    
    await message.answer(text)

# --- 7. РАЗВЛЕЧЕНИЯ ---
@base_router.message(Command("dice"))
async def play_dice(message: Message):
    await message.answer_dice(emoji="🎲")

@base_router.message(Command("darts"))
async def play_darts(message: Message):
    await message.answer_dice(emoji="🎯")

@base_router.message(Command("who"))
async def who_is_it(message: Message):
    tasks = ["идёт за хлебом 🥖", "моет посуду 🍽", "выбирает фильм 🎬", "выносит мусор 🗑"]
    task = random.choice(tasks)
    await message.answer(f"Сегодня <b>{message.from_user.first_name}</b> {task}!")

@base_router.message(Command("напомни", "remind"))
async def set_reminder(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Формат: <code>/remind 10 текст</code>")
        return
    try:
        minutes = int(args[1])
        msg = args[2]
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
        "/buy • /list • /clear • /удалить\n"
        "/quote • /phrase\n"
        "/др Имя ДД.ММ\n"
        "/погода [город]\n"
        "/knb • /knbtop\n"
        "/remind • /rating • /who"
    )

# --- КНОПКИ ---
@base_router.callback_query(lambda c: c.data == "help_callback")
async def process_callback_help(callback_query: CallbackQuery):
    await callback_query.message.answer(
        "<b>Справка:</b>\n\n"
        "🛒 /buy [товар]\n"
        "🛒 /list • /удалить [номер]\n"
        "📜 /phrase\n"
        "🎉 /др Имя ДД.ММ\n"
        "🌤️ /погода [город]\n"
        "🎮 /knb — игра с ботом\n"
        "⏰ /remind [мин] [текст]"
    )
    await callback_query.answer()

@base_router.callback_query(lambda c: c.data == "rating_callback")
async def process_callback_rating(callback_query: CallbackQuery):
    await show_rating(callback_query.message)
    await callback_query.answer()

# --- SCHEDULER ФУНКЦИИ ---
async def send_daily_motivation(bot):
    chat_id = -1001130889326
    
    # Цитата
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
    
    # Погода
    weather_text = await get_weather("Москва")  # Измените город при необходимости
    
    full_text = (
        f"<b>☀️ Доброе утро, любимая семья! ☀️</b>\n\n"
        f"{quote_text}\n\n"
        f"{weather_text}\n\n"
        f"С любовью от вашего бота 🌹"
    )
    
    # Фото
    keywords = ["family morning", "good morning", "happy family", "cozy breakfast", "sunrise family"]
    query = random.choice(keywords)
    photo_url = f"https://source.unsplash.com/featured/800x600/?{query.replace(' ', '%20')}"
    
    await bot.send_photo(chat_id, photo_url, caption=full_text)

async def send_birthday_reminders(bot):
    chat_id = -1001130889326
    today = datetime.now()
    
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, day, month FROM birthdays')
    await conn.close()
    
    reminders = []
    for row in rows:
        bday = datetime(today.year, row['month'], row['day'])
        if bday < today.replace(hour=0, minute=0, second=0, microsecond=0):
            bday = datetime(today.year + 1, row['month'], row['day'])
        days_left = (bday - today).days
        
        if 0 <= days_left <= 7:
            if days_left == 0:
                reminders.append(f"🎂 <b>СЕГОДНЯ</b> ДР у <b>{row['name']}</b>! 🥳")
            elif days_left == 1:
                reminders.append(f"⚡ Завтра ДР у <b>{row['name']}</b>!")
            else:
                reminders.append(f"📅 {row['name']} — {row['day']:02d}.{row['month']:02d} (через {days_left} дн.)")
    
    if reminders:
        text = "<b>🎉 Ближайшие дни рождения:</b>\n\n" + "\n".join(reminders)
        await bot.send_message(chat_id, text)
