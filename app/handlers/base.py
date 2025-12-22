import os
import random
import asyncio
import asyncpg
import logging
import urllib.parse
from datetime import datetime
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# --- ГЕНЕРАЦИЯ КАРТИНОК ---
@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer("Напиши описание. Пример: <code>/gen рыжий кот в космосе</code>")
    
    waiting_msg = await message.answer("🎨 Рисую... Подождите немного.")
    
    # Кодируем запрос для URL
    encoded_prompt = urllib.parse.quote(prompt)
    # Используем Pollinations AI (бесплатно и без ключей)
    image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed={random.randint(1, 1000)}&model=flux"
    
    try:
        await message.answer_photo(
            photo=image_url,
            caption=f"✨ Результат по запросу: <i>{prompt}</i>"
        )
        await waiting_msg.delete()
    except Exception as e:
        await waiting_msg.edit_text(f"❌ Не удалось создать картинку. Попробуйте другой запрос.")

# --- РУССКАЯ МОТИВАЦИЯ ---
async def get_russian_quote():
    quotes = [
        "Семья — это не главное. Семья — это всё. 🏠",
        "Счастлив тот, кто счастлив у себя дома. ✨",
        "Успех — это сумма маленьких усилий, повторяющихся день за днем. 💪",
        "Дом там, где тебя всегда ждут. 🗝",
        "Семья — это маленький мир, созданный любовью. 🌍",
        "Величайшее счастье — быть уверенным, что тебя любят. ❤️"
    ]
    return random.choice(quotes)

async def send_motivation_to_chat(bot: Bot, chat_id: int):
    quote = await get_russian_quote()
    photo_url = f"https://picsum.photos/800/600?nature,water&sig={random.randint(1, 1000)}"
    try:
        await bot.send_photo(chat_id, photo_url, caption=f"<b>Доброе утро! ☀️</b>\n\n{quote}")
    except:
        await bot.send_message(chat_id, f"<b>Доброе утро! ☀️</b>\n\n{quote}")

# --- СТАРТ И КНОПКИ ---
@base_router.message(Command("start"))
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Создать шедевр", callback_data="btn_gen")],
        [InlineKeyboardButton(text="✨ Мотивация", callback_data="btn_moti")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="btn_rate")]
    ])
    await message.answer(f"Привет, {message.from_user.first_name}! Я твой Домовой.\nИспользуй /gen для картинок или кнопки ниже:", reply_markup=kb)

@base_router.callback_query(F.data == "btn_moti")
async def cb_moti(call: types.CallbackQuery, bot: Bot):
    await send_motivation_to_chat(bot, call.message.chat.id)
    await call.answer()

@base_router.callback_query(F.data == "btn_gen")
async def cb_gen(call: types.CallbackQuery):
    await call.message.answer("Чтобы создать картинку, напиши: <code>/gen твой запрос</code>")
    await call.answer()

# --- ОСТАЛЬНЫЕ КОМАНДЫ ---
@base_router.message(Command("who"))
async def cmd_who(message: Message):
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT name FROM reputation ORDER BY RANDOM() LIMIT 1')
    await conn.close()
    name = row['name'] if row else message.from_user.first_name
    await message.answer(f"🎯 Сегодня ответственный: <b>{name}</b>!")

@base_router.message(F.text == "+")
async def add_rep(message: Message):
    if not message.reply_to_message or message.reply_to_message.from_user.id == message.from_user.id: return
    conn = await get_db_connection()
    await conn.execute('INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1) ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1', 
                       message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    await conn.close()
    await message.answer(f"➕ Репутация {message.reply_to_message.from_user.first_name} повышена!")

@base_router.message(Command("buy"))
async def cmd_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if item:
        conn = await get_db_connection()
        await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
        await conn.close()
        await message.answer(f"✅ Добавлено: {item}")

@base_router.message(Command("list"))
async def cmd_list(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    if not rows: return await message.answer("Список пуст.")
    await message.answer("<b>🛒 Список покупок:</b>\n" + "\n".join([f"• {r['item']}" for r in rows]))

@base_router.message(Command("clear"))
async def cmd_clear(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список очищен!")

@base_router.message(Command("dbtest"))
async def db_test(message: Message):
    try:
        conn = await get_db_connection()
        await conn.close()
        await message.answer("✅ База данных подключена!")
    except Exception as e:
        await message.answer(f"❌ Ошибка БД: {e}")

# Инициализация таблиц
async def init_db():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS reputation (user_id BIGINT PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS shopping_list (id SERIAL PRIMARY KEY, item TEXT);
        CREATE TABLE IF NOT EXISTS birthdays (id SERIAL PRIMARY KEY, name TEXT, birth_date DATE);
    ''')
    await conn.close()
from PIL import Image, ImageOps, ImageEnhance
import io

# --- ОБРАБОТКА ФОТО ---

@base_router.message(F.photo)
async def handle_photo(message: Message):
    """Ловит отправленное фото и предлагает действия"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔘 Ч/Б", callback_data="edit_bw"),
            InlineKeyboardButton(text="🔄 Инверсия", callback_data="edit_inv")
        ],
        [
            InlineKeyboardButton(text="☀️ Яркость +", callback_data="edit_bright"),
            InlineKeyboardButton(text="🎨 Контраст", callback_data="edit_cont")
        ]
    ])
    await message.reply("Красивое фото! Хочешь применить фильтр?", reply_markup=kb)

@base_router.callback_query(F.data.startswith("edit_"))
async def edit_callback(call: types.CallbackQuery, bot: Bot):
    # 1. Получаем фото, на которое ответил пользователь
    photo = call.message.reply_to_message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    
    # 2. Скачиваем в память (BytesIO)
    file_content = await bot.download_file(file_info.file_path)
    img = Image.open(file_content)
    
    action = call.data.split("_")[1]
    
    # 3. Применяем фильтр
    if action == "bw":
        img = ImageOps.grayscale(img)
    elif action == "inv":
        img = ImageOps.invert(img.convert("RGB"))
    elif action == "bright":
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.5)
    elif action == "cont":
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)

    # 4. Сохраняем результат обратно в байты
    output = io.BytesIO()
    img.save(output, format="JPEG")
    output.seek(0)

    # 5. Отправляем результат
    await bot.send_photo(
        call.message.chat.id, 
        types.BufferedInputFile(output.read(), filename="edit.jpg"),
        caption="Готово! ✨"
    )
    await call.answer()
