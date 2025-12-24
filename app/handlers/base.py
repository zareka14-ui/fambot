import os
import random
import logging
import io
from datetime import datetime, timezone

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
    hf_img2img,
    hf_remove_bg,  # <-- Добавлено
    GFPGAN_MODEL,
    ESRGAN_MODEL
)

base_router = Router()

GEN_COOLDOWN = {}
COOLDOWN_SEC = 20

# ====== IMAGE GENERATION ======
@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer("Пример: <code>/gen cinematic cat</code>")

    uid = message.from_user.id
    now = datetime.now(timezone.utc).timestamp()

    if uid in GEN_COOLDOWN and now - GEN_COOLDOWN[uid] < COOLDOWN_SEC:
        return await message.answer("⏳ Подожди 20 секунд")

    GEN_COOLDOWN[uid] = now
    status = await message.answer("🎨 Генерирую изображение…")

    enhanced_prompt = f"{prompt}, ultra detailed, masterpiece, sharp focus"
    image = await generate_best(enhanced_prompt)

    if not image:
        return await status.edit_text("❌ Генерация временно недоступна")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✨ Лицо", callback_data="facefix"),
            InlineKeyboardButton(text="🔍 Апскейл", callback_data="upscale")
        ]
    ])

    await message.answer_photo(
        BufferedInputFile(image, filename="gen.png"),
        caption=f"✨ <b>Готово</b>\n<i>{prompt}</i>",
        reply_markup=kb
    )
    await status.delete()

# ====== STYLE / IMG2IMG ======
@base_router.message(Command("style"))
async def cmd_style(message: Message):
    prompt = message.text.replace("/style", "").strip()
    if not prompt:
        return await message.answer("Напиши стиль! Пример: ответь на фото командой <code>/style в стиле аниме</code>")

    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.answer("Ответь этой командой на фотографию!")

    status = await message.answer("🎨 Перерисовываю фото...")
    
    try:
        # Скачиваем фото в объект BytesIO
        photo = message.reply_to_message.photo[-1]
        file_dest = io.BytesIO()
        await message.bot.download(photo, destination=file_dest)
        img_bytes = file_dest.getvalue()
        
        result = await hf_img2img(img_bytes, prompt)
        
        if result:
            await message.answer_photo(
                BufferedInputFile(result, filename="styled.png"),
                caption=f"✨ Новый стиль: {prompt}"
            )
        else:
            await message.answer("❌ Не удалось стилизовать. Попробуй SD 1.5 позже.")
    except Exception as e:
        logging.error(f"Style error: {e}")
        await message.answer("❌ Ошибка при обработке.")
    finally:
        await status.delete()

# ====== REMOVE BACKGROUND ======
@base_router.message(Command("nobg"))
async def cmd_remove_bg(message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.answer("Ответь этой командой на фото!")

    status = await message.answer("✂️ Удаляю фон...")
    try:
        photo = message.reply_to_message.photo[-1]
        file_dest = io.BytesIO()
        await message.bot.download(photo, destination=file_dest)
        
        result = await hf_remove_bg(file_dest.getvalue())
        
        if result:
            # Отправляем документом, чтобы сохранить прозрачность PNG
            await message.answer_document(
                BufferedInputFile(result, filename="no_bg.png"),
                caption="✨ Фон удален"
            )
        else:
            await message.answer("❌ Ошибка удаления фона.")
    except Exception as e:
        logging.error(f"NoBG error: {e}")
        await message.answer("❌ Произошла ошибка.")
    finally:
        await status.delete()

# ====== CALLBACKS ======
@base_router.callback_query(F.data == "facefix")
async def facefix(call: types.CallbackQuery):
    await call.answer()
    if not call.message.photo: return
    
    status = await call.message.answer("✨ Улучшаю лицо...")
    file_dest = io.BytesIO()
    await call.bot.download(call.message.photo[-1], destination=file_dest)
    
    result = await hf_image_process(file_dest.getvalue(), GFPGAN_MODEL)
    if result:
        await call.message.answer_photo(BufferedInputFile(result, filename="fixed.png"), caption="✨ Лицо улучшено")
    else:
        await call.message.answer("❌ Ошибка HF.")
    await status.delete()

# ... (остальные команды типа + и start оставляем без изменений)
