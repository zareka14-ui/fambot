import os
import random
import logging
from datetime import datetime

from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile
)

from app.services.db import get_db
from app.services.ai_image import (
    generate_best,
    hf_image_process,
    hf_img2img,      # <--- ОБЯЗАТЕЛЬНО ДОБАВИТЬ ЭТУ СТРОКУ
    GFPGAN_MODEL,
    ESRGAN_MODEL
)

base_router = Router()

GEN_COOLDOWN = {}
COOLDOWN_SEC = 20

# ====== DB INIT ======
async def init_db():
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS reputation (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            score INTEGER DEFAULT 0
        )
        """)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS shopping_list (
            id SERIAL PRIMARY KEY,
            item TEXT
        )
        """)

# ====== IMAGE GENERATION ======
@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer("Пример: <code>/gen cinematic cat</code>")

    uid = message.from_user.id
    now = datetime.utcnow().timestamp()

    if uid in GEN_COOLDOWN and now - GEN_COOLDOWN[uid] < COOLDOWN_SEC:
        return await message.answer("⏳ Подожди 20 секунд")

    GEN_COOLDOWN[uid] = now
    status = await message.answer("🎨 Генерирую изображение…")

    enhanced_prompt = f"{prompt}, ultra detailed, masterpiece, sharp focus"
    image = await generate_best(enhanced_prompt)

    if not image:
        return await status.edit_text("❌ Генерация временно недоступна")

    # Твои кнопки
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✨ Лицо", callback_data="facefix"),
            InlineKeyboardButton(text="🔍 Апскейл", callback_data="upscale")
        ]
    ])

    await message.answer_photo(
        BufferedInputFile(image, "gen.png"),
        caption=f"✨ <b>Готово</b>\n<i>{prompt}</i>",
        reply_markup=kb
    )
    await status.delete()

# ====== ОБРАБОТКА ФОТО (FACEFIX / UPSCALE) ======
@base_router.callback_query(F.data == "facefix")
async def facefix(call: types.CallbackQuery):
    await call.answer()
    if not call.message.photo: return
    
    file = await call.bot.download(call.message.photo[-1])
    status = await call.message.answer("✨ Улучшаю лицо (GFPGAN)...")
    
    result = await hf_image_process(file.read(), GFPGAN_MODEL)
    if result:
        await call.message.answer_photo(BufferedInputFile(result, "fixed.png"), caption="✨ Лицо улучшено")
    else:
        await call.message.answer("❌ HF не ответил. Попробуй позже.")
    await status.delete()

@base_router.callback_query(F.data == "upscale")
async def upscale(call: types.CallbackQuery):
    await call.answer()
    if not call.message.photo: return
    
    file = await call.bot.download(call.message.photo[-1])
    status = await call.message.answer("🔍 Увеличиваю разрешение (ESRGAN)...")
    
    result = await hf_image_process(file.read(), ESRGAN_MODEL)
    if result:
        await call.message.answer_photo(BufferedInputFile(result, "big.png"), caption="🔍 Апскейл завершен")
    else:
        await call.message.answer("❌ Ошибка апскейла.")
    await status.delete()

# ====== REPUTATION / SHOPPING ======
@base_router.message(F.text == "+")
async def add_rep(message: Message):
    if not message.reply_to_message or message.reply_to_message.from_user.id == message.from_user.id:
        return
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO reputation (user_id, name, score) VALUES ($1, $2, 1) ON CONFLICT (user_id) DO UPDATE SET score = reputation.score + 1",
                           message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    await message.answer(f"👍 Репутация {message.reply_to_message.from_user.first_name} +1")

@base_router.message(Command("start"))
async def start(message: Message):
    await message.answer("🏠 <b>Домовой на связи!</b>\n/gen — Рисовать\n/rating — Рейтинг")

async def send_motivation_to_chat(bot: Bot, chat_id: int):
    try:
        await bot.send_message(chat_id, "☀️ <b>Доброе утро, семья!</b>")
    except: pass
@base_router.message(Command("style"))
async def cmd_style(message: Message):
    # Проверка на наличие текста (промпта) и фото
    prompt = message.text.replace("/style", "").strip()
    if not prompt:
        return await message.answer("Напиши стиль! Пример: ответь на фото командой <code>/style в стиле киберпанк</code>")

    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.answer("Ответь этой командой на фотографию!")

    status = await message.answer("🎨 Перерисовываю фото... подожди немного.")
    
    try:
        # Скачиваем фото
        file = await message.bot.download(message.reply_to_message.photo[-1])
        img_bytes = file.read()
        
        # Вызываем нашу новую функцию
        result = await hf_img2img(img_bytes, prompt)
        
        if result:
            await message.answer_photo(
                BufferedInputFile(result, filename="styled.png"),
                caption=f"✨ Новый стиль: {prompt}"
            )
        else:
            await message.answer("❌ Не удалось стилизовать. Попробуй другой промпт или подожди минуту.")
    except Exception as e:
        logging.error(f"Style error: {e}")
        await message.answer("❌ Произошла ошибка.")
    finally:
        await status.delete()

