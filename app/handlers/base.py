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
    GFPGAN_MODEL,
    ESRGAN_MODEL
)

base_router = Router()

# ====== НАСТРОЙКИ ======
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
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS birthdays (
            id SERIAL PRIMARY KEY,
            name TEXT,
            birth_date DATE
        )
        """)

# ====== IMAGE GENERATION ======
@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer(
            "Пример:\n<code>/gen cinematic cyberpunk cat</code>"
        )

    uid = message.from_user.id
    now = datetime.utcnow().timestamp()

    if uid in GEN_COOLDOWN and now - GEN_COOLDOWN[uid] < COOLDOWN_SEC:
        return await message.answer("⏳ Подожди 20 секунд")

    GEN_COOLDOWN[uid] = now

    status = await message.answer("🎨 Генерирую изображение…")

    enhanced_prompt = (
        f"{prompt}, ultra detailed, cinematic lighting, "
        f"8k, masterpiece, sharp focus"
    )

    image = await generate_best(enhanced_prompt)

    if not image:
        return await status.edit_text("❌ Генерация временно недоступна")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔁 Ещё",
                callback_data=f"regen:{prompt}"
            ),
            InlineKeyboardButton(
                text="✨ Лицо",
                callback_data="facefix"
            ),
            InlineKeyboardButton(
                text="🔍 Апскейл",
                callback_data="upscale"
            )
        ]
    ])

    await message.answer_photo(
        BufferedInputFile(image, "gen.png"),
        caption=f"✨ <b>Готово</b>\n<i>{prompt}</i>",
        reply_markup=kb
    )

    await status.delete()


@base_router.callback_query(F.data.startswith("regen:"))
async def regen(call: types.CallbackQuery):
    prompt = call.data.split(":", 1)[1]
    await call.answer()
    await cmd_generate(
        Message(
            message_id=call.message.message_id,
            from_user=call.from_user,
            chat=call.message.chat,
            text=f"/gen {prompt}"
        )
    )

# ====== IMAGE PROCESSING ======
@base_router.callback_query(F.data == "facefix")
async def facefix(call: types.CallbackQuery):
    await call.answer()

    if not call.message.reply_to_message or not call.message.reply_to_message.photo:
        return await call.message.answer("Ответь этой кнопкой на фото")

    photo = call.message.reply_to_message.photo[-1]
    file = await call.bot.download(photo)

    status = await call.message.answer("✨ Улучшаю лицо…")

    result = await hf_image_process(file.read(), GFPGAN_MODEL)

    if result:
        await call.message.answer_photo(
            BufferedInputFile(result, "facefix.png"),
            caption="✨ Лицо улучшено"
        )
    else:
        await call.message.answer("❌ Не удалось обработать фото")

    await status.delete()


@base_router.callback_query(F.data == "upscale")
async def upscale(call: types.CallbackQuery):
    await call.answer()

    if not call.message.reply_to_message or not call.message.reply_to_message.photo:
        return await call.message.answer("Ответь этой кнопкой на фото")

    photo = call.message.reply_to_message.photo[-1]
    file = await call.bot.download(photo)

    status = await call.message.answer("🔍 Увеличиваю разрешение…")

    result = await hf_image_process(file.read(), ESRGAN_MODEL)

    if result:
        await call.message.answer_photo(
            BufferedInputFile(result, "upscale.png"),
            caption="🔍 Апскейл завершён"
        )
    else:
        await call.message.answer("❌ Не удалось увеличить изображение")

    await status.delete()

# ====== REPUTATION ======
@base_router.message(F.text == "+")
async def add_rep(message: Message):
    if not message.reply_to_message:
        return
    if message.reply_to_message.from_user.id == message.from_user.id:
        return

    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO reputation (user_id, name, score)
        VALUES ($1, $2, 1)
        ON CONFLICT (user_id)
        DO UPDATE SET score = reputation.score + 1
        """,
        message.reply_to_message.from_user.id,
        message.reply_to_message.from_user.first_name
        )

    await message.answer(
        f"👍 Репутация <b>{message.reply_to_message.from_user.first_name}</b> +1"
    )


@base_router.message(Command("rating"))
async def rating(message: Message):
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name, score FROM reputation ORDER BY score DESC"
        )

    if not rows:
        return await message.answer("🏆 Рейтинг пока пуст")

    text = "<b>🏆 Рейтинг семьи:</b>\n" + "\n".join(
        f"{r['name']}: {r['score']}" for r in rows
    )

    await message.answer(text)

# ====== SHOPPING LIST ======
@base_router.message(Command("buy"))
async def buy(message: Message):
    item = message.text.replace("/buy", "").strip()
    if not item:
        return

    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO shopping_list (item) VALUES ($1)",
            item
        )

    await message.answer(f"🛒 Добавлено: {item}")


@base_router.message(Command("list"))
async def list_items(message: Message):
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT item FROM shopping_list")

    if not rows:
        return await message.answer("🛒 Список пуст")

    text = "<b>🛒 Нужно купить:</b>\n" + "\n".join(
        f"• {r['item']}" for r in rows
    )

    await message.answer(text)


@base_router.message(Command("clear"))
async def clear_list(message: Message):
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM shopping_list")

    await message.answer("🧹 Список очищен")

# ====== START ======
@base_router.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "🏠 <b>Домовой на связи!</b>\n\n"
        "🎨 /gen — генерация изображения\n"
        "🛒 /buy — добавить покупку\n"
        "📊 /rating — рейтинг семьи\n"
        "➕ '+' — поднять репутацию"
    )

# ====== MORNING ======
async def send_motivation_to_chat(bot: Bot, chat_id: int):
    url = f"https://picsum.photos/800/600?sig={random.randint(1,999)}"
    try:
        await bot.send_photo(
            chat_id,
            url,
            caption="☀️ <b>Доброе утро, семья!</b>\nПусть день будет отличным ✨"
        )
    except Exception:
        await bot.send_message(
            chat_id,
            "☀️ <b>Доброе утро!</b>"
        )
