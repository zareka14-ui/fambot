import os
import random
import asyncio
import asyncpg
import logging
import aiohttp  # Нужно для запросов к онлайн API
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

# --- ОНЛАЙН ОБНОВЛЕНИЕ МОТИВАЦИИ ---
async def get_online_quote():
    """Получает случайную цитату из сети (на английском) или использует расширенный список."""
    try:
        # Пытаемся взять цитату из API
        async with aiohttp.ClientSession() as session:
            async with session.get("https://zenquotes.io/api/random") as response:
                if response.status == 200:
                    data = await response.json()
                    return f"<i>«{data[0]['q']}»</i>\n\n— <b>{data[0]['a']}</b>"
    except Exception as e:
        logging.error(f"Quote API error: {e}")
    
    # Резервный расширенный список на русском, если API недоступно
    backup_quotes = [
        "Семья — это не главное. Семья — это всё.",
        "Успех — это идти от ошибки к ошибке, не теряя энтузиазма.",
        "Единственный способ сделать выдающуюся работу — искренне любить то, что делаешь.",
        "Твое время ограничено, не трать его, живя чужой жизнью.",
        "Препятствия — это те страшные вещи, которые вы видите, когда отводите взгляд от цели.",
        "Не ждите идеального момента. Берите момент и делайте его идеальным.",
        "Счастье не в том, чтобы иметь всё, а в том, чтобы ценить то, что есть."
    ]
    return f"✨ <i>{random.choice(backup_quotes)}</i>"

async def send_motivation_to_chat(bot, chat_id: int):
    """Функция для утренней рассылки и ручной команды."""
    quote = await get_online_quote()
    photo_url = f"https://picsum.photos/800/600?random={random.randint(1, 1000)}" # Всегда случайное фото
    try:
        await bot.send_photo(
            chat_id, 
            photo_url, 
            caption=f"<b>Заряд бодрости на сегодня! 💪</b>\n\n{quote}",
            parse_mode="HTML"
        )
    except Exception:
        await bot.send_message(chat_id, f"<b>Доброе утро! ✨</b>\n\n{quote}", parse_mode="HTML")

# --- КОМАНДА МОТИВАЦИИ ---
@base_router.message(Command("motivation"))
async def cmd_motivation(message: Message, bot: types.Bot):
    await send_motivation_to_chat(bot, message.chat.id)

# --- РЕПУТАЦИЯ И РЕЙТИНГ ---
@base_router.message(F.text == "+")
async def add_rep(message: Message):
    if not message.reply_to_message: return
    if message.reply_to_message.from_user.id == message.from_user.id:
        return await message.answer("Нельзя хвалить самого себя! 😉")
    
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1
    ''', message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    await conn.close()
    await message.answer(f"➕ Репутация <b>{message.reply_to_message.from_user.first_name}</b> повышена!")

@base_router.message(Command("rating"))
async def cmd_rating(message: Message):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC LIMIT 10')
    await conn.close()
    if not rows: return await message.answer("Рейтинг пуст.")
    res = "<b>🏆 Топ помощников:</b>\n" + "\n".join([f"• {r['name']}: {r['score']}" for r in rows])
    await message.answer(res)

# --- ИГРЫ (DICE, DARTS, KNB) ---
@base_router.message(Command("dice"))
async def cmd_dice(message: Message): await message.answer_dice(emoji="🎲")

@base_router.message(Command("darts"))
async def cmd_darts(message: Message): await message.answer_dice(emoji="🎯")

@base_router.message(Command("knb"))
async def cmd_knb(message: Message):
    v = ["Камень ✊", "Ножницы ✌️", "Бумага ✋"]
    await message.answer(f"Мой выбор: <b>{random.choice(v)}</b>")

# --- КТО ДЕЖУРНЫЙ (WHO) ---
@base_router.message(Command("who"))
async def cmd_who(message: Message):
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow('SELECT name FROM reputation ORDER BY RANDOM() LIMIT 1')
    await conn.close()
    name = row['name'] if row else message.from_user.first_name
    await message.answer(f"🎯 Сегодня дежурный: <b>{name}</b>!")

# --- СПИСОК ПОКУПОК ---
@base_router.message(Command("buy"))
async def cmd_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if item:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
        await conn.close()
        await message.answer(f"✅ Добавлено: {item}")

@base_router.message(Command("list"))
async def cmd_list(message: Message):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    if not rows: return await message.answer("Список пуст.")
    await message.answer("<b>🛒 Купить:</b>\n" + "\n".join([f"• {r['item']}" for r in rows]))

@base_router.message(Command("clear"))
async def cmd_clear(message: Message):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список очищен!")

# --- НАПОМИНАНИЯ (REMIND) ---
@base_router.message(Command("remind"))
async def cmd_remind(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3: return await message.answer("Пример: /remind 5 Покормить кота")
    try:
        m, t = int(args[1]), args[2]
        await message.answer(f"⏰ Ок, напомню через {m} мин.")
        await asyncio.sleep(m * 60)
        await message.reply(f"🔔 <b>НАПОМИНАНИЕ:</b>\n{t}")
    except: await message.answer("Ошибка в формате.")

# --- УЖИН (DINNER) ---
@base_router.message(Command("dinner"))
async def cmd_dinner(message: Message):
    await message.answer_poll("Что на ужин? 🥘", ["Домашнее 🥗", "Пицца 🍕", "Суши 🍣", "Бургеры 🍔"], is_anonymous=False)

# --- ДНИ РОЖДЕНИЯ ---
@base_router.message(Command("add_bd"))
async def add_bd(message: Message):
    a = message.text.split()
    if len(a) < 3: return await message.answer("Формат: /add_bd Имя ДД.ММ Категория")
    try:
        d, m = map(int, a[2].split('.'))
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute('INSERT INTO birthdays (name, birth_date, category) VALUES ($1, $2, $3)', a[1], datetime(2000, m, d), a[3] if len(a)>3 else "Друг")
        await conn.close()
        await message.answer(f"🎂 Сохранил: {a[1]}")
    except: await message.answer("Ошибка в дате.")

@base_router.message(Command("all_bd"))
async def all_bd(message: Message):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch('SELECT name, birth_date FROM birthdays ORDER BY EXTRACT(MONTH FROM birth_date)')
    await conn.close()
    if not rows: return await message.answer("Календарь пуст.")
    res = "<b>📅 События:</b>\n" + "\n".join([f"• {r['birth_date'].strftime('%d.%m')} — {r['name']}" for r in rows])
    await message.answer(res)

# --- ПОМОЩЬ ---
@base_router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>🏠 Все команды Домового:</b>\n\n"
        "✨ /motivation - получить цитату\n"
        "🎯 /who - дежурный\n"
        "🎲 /dice, /darts, /knb - игры\n"
        "🏆 /rating - рейтинг (+ за помощь)\n"
        "🛒 /buy, /list, /clear - покупки\n"
        "⏰ /remind [мин] [текст]\n"
        "🥘 /dinner - опрос по еде\n"
        "🎂 /add_bd, /all_bd - дни рождения"
    )

@base_router.message(Command("id"))
async def get_id(message: Message): await message.answer(f"ID чата: <code>{message.chat.id}</code>")
