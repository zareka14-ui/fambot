import os
import random
import asyncio
import asyncpg
import logging
import urllib.parse
import aiohttp
import base64
import json
from datetime import datetime
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")
SEGMIND_API_KEY = os.getenv("SEGMIND_API_KEY")

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# --- ИНИЦИАЛИЗАЦИЯ БД ---
async def init_db():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS reputation (user_id BIGINT PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS shopping_list (id SERIAL PRIMARY KEY, item TEXT);
        CREATE TABLE IF NOT EXISTS birthdays (id SERIAL PRIMARY KEY, name TEXT, birth_date DATE);
    ''')
    await conn.close()

# --- ВЫСОКОКАЧЕСТВЕННАЯ ГЕНЕРАЦИЯ (SEGMIND) ---
@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer("Напиши описание. Пример: <code>/gen ковбой в открытом космосе, реализм</code>")
    
    if not SEGMIND_API_KEY:
        return await message.answer("❌ Ошибка: Не настроен API-ключ Segmind.")

    msg = await message.answer("🎨 Рисую шедевр через SDXL... Пожалуйста, подождите.")
    
    url = "https://api.segmind.com/v1/sdxl1.0-txt2img"
    data = {
        "prompt": prompt,
        "negative_prompt": "ugly, blurry, low quality, distorted, watermark",
        "style": "base",
        "samples": 1,
        "scheduler": "dpmpp_2m",
        "num_inference_steps": 25,
        "guidance_scale": 7.5,
        "seed": random.randint(1, 9999999),
        "img_width": 1024,
        "img_height": 1024
    }

    headers = {"x-api-key": SEGMIND_API_KEY, "Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    await message.answer_photo(
                        photo=BufferedInputFile(image_data, filename="gen.jpg"),
                        caption=f"✨ <b>Результат:</b> {prompt}"
                    )
                    await msg.delete()
                else:
                    await msg.edit_text("❌ Ошибка API или закончились лимиты Segmind.")
    except Exception as e:
        logging.error(f"Gen error: {e}")
        await msg.edit_text("❌ Произошла техническая ошибка.")

# --- УМНОЕ РЕДАКТИРОВАНИЕ ФОТО (SEGMIND) ---
@base_router.message(F.photo)
async def handle_ai_edit(message: Message, bot: Bot):
    if not message.caption:
        return await message.answer("📸 Чтобы изменить фото, пришли его с <b>описанием</b>!\nНапример: <i>'сделай меня киборгом'</i>")

    if not SEGMIND_API_KEY:
        return await message.answer("❌ API ключ Segmind не настроен.")

    msg = await message.answer("🤖 Перерисовываю фото с сохранением структуры...")

    # Скачиваем фото
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    photo_bytes = await bot.download_file(file_info.file_path)
    encoded_image = base64.b64encode(photo_bytes.read()).decode('utf-8')

    url = "https://api.segmind.com/v1/sdxl1.0-img2img"
    data = {
        "image": encoded_image,
        "prompt": message.caption.strip(),
        "negative_prompt": "deformed, ugly, blurry, low quality",
        "samples": 1,
        "scheduler": "dpmpp_2m",
        "num_inference_steps": 30,
        "guidance_scale": 8.0,
        "strength": 0.5,  # Баланс между оригиналом и промптом
        "seed": random.randint(1, 9999999)
    }

    headers = {"x-api-key": SEGMIND_API_KEY, "Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    await message.answer_photo(
                        photo=BufferedInputFile(image_data, filename="edit.jpg"),
                        caption=f"🎨 <b>Обработка готова!</b>\nЗапрос: {message.caption}"
                    )
                    await msg.delete()
                else:
                    await msg.edit_text("❌ Не удалось обработать. Проверьте лимиты Segmind.")
    except Exception as e:
        logging.error(f"Edit error: {e}")
        await msg.edit_text("❌ Ошибка связи с нейросетью.")

# --- БАЗОВЫЕ КОМАНДЫ (ПОКУПКИ, РЕЙТИНГ, ПРАЗДНИКИ) ---
@base_router.message(Command("buy"))
async def cmd_buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if item:
        conn = await get_db_connection()
        await conn.execute('INSERT INTO shopping_list (item) VALUES ($1)', item)
        await conn.close()
        await message.answer(f"✅ Добавлено в список: {item}")

@base_router.message(Command("list"))
async def cmd_list(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT item FROM shopping_list')
    await conn.close()
    res = "<b>🛒 Список покупок:</b>\n" + "\n".join([f"• {r['item']}" for r in rows]) if rows else "Список пуст."
    await message.answer(res)

@base_router.message(Command("clear"))
async def cmd_clear(message: Message):
    conn = await get_db_connection()
    await conn.execute('DELETE FROM shopping_list')
    await conn.close()
    await message.answer("🧹 Список очищен!")

@base_router.message(F.text == "+")
async def add_rep(message: Message):
    if not message.reply_to_message or message.reply_to_message.from_user.id == message.from_user.id: return
    conn = await get_db_connection()
    await conn.execute('''
        INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1)
        ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1
    ''', message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    await conn.close()
    await message.answer(f"➕ Репутация {message.reply_to_message.from_user.first_name} повышена!")

@base_router.message(Command("all_bd"))
async def list_birthdays(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, birth_date FROM birthdays ORDER BY EXTRACT(MONTH FROM birth_date), EXTRACT(DAY FROM birth_date)')
    await conn.close()
    if not rows: return await message.answer("📅 Календарь пуст.")
    res = "<b>📅 Дни рождения:</b>\n" + "\n".join([f"• {r['birth_date'].strftime('%d.%m')} — {r['name']}" for r in rows])
    await message.answer(res)

@base_router.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(f"ID этого чата: <code>{message.chat.id}</code>")

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Создать фото", callback_data="info_ai")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="info_rating")]
    ])
    await message.answer("🏠 Привет! Я твой обновленный Домовой. Теперь с мощным ИИ Segmind!\nОтправь /gen для рисования или фото с текстом для обработки.", reply_markup=kb)

@base_router.callback_query(F.data == "info_ai")
async def info_ai(call: types.CallbackQuery):
    await call.message.answer("Пиши <code>/gen [описание]</code> для новых картинок.\nПрисылай фото с подписью для изменения стиля.")
    await call.answer()

async def send_motivation_to_chat(bot: Bot, chat_id: int):
    url = f"https://picsum.photos/800/600?nature&sig={random.randint(1,1000)}"
    try:
        await bot.send_photo(chat_id, url, caption="<b>Доброе утро!</b>\nПусть этот день будет продуктивным. ✨")
    except:
        await bot.send_message(chat_id, "<b>Доброе утро! ✨</b>")
