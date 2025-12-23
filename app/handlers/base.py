import os
import random
import asyncio
import asyncpg
import logging
import urllib.parse
import aiohttp
from datetime import datetime
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")
HF_TOKEN = os.getenv("HF_TOKEN")

# Пытаемся использовать официальную модель SDXL 1.0
HF_MODEL_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# --- ИИ ГЕНЕРАЦИЯ (Hugging Face) ---
async def query_hugging_face(prompt: str):
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {"negative_prompt": "blurry, bad quality, distorted"}
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(HF_MODEL_URL, headers=headers, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    return await resp.read()
                elif resp.status == 503:
                    return "loading"
                else:
                    # Возвращаем сам код ошибки для диагностики
                    return f"error_{resp.status}"
        except Exception as e:
            logging.error(f"HF Request error: {e}")
            return f"exception_{str(e)[:20]}"

@base_router.message(Command("gen"))
async def cmd_generate(message: Message):
    prompt = message.text.replace("/gen", "").strip()
    if not prompt:
        return await message.answer("Напиши описание. Пример: <code>/gen киберпанк город</code>")
    
    if not HF_TOKEN:
        return await message.answer("❌ Ошибка: В Render не прописан HF_TOKEN")

    msg = await message.answer("🎨 Запрашиваю нейросеть Hugging Face...")
    
    # Добавляем детали для улучшения картинки
    enhanced_prompt = f"{prompt}, professional digital art, masterpiece, high resolution"
    result = await query_hugging_face(enhanced_prompt)

    if result == "loading":
        await msg.edit_text("⏳ Модель загружается в память сервера. Это нормально. Повтори через 30 секунд!")
    elif isinstance(result, str) and result.startswith("error_"):
        code = result.split("_")[1]
        await msg.edit_text(f"❌ Сервер ответил кодом: {code}. Возможно, модель переехала или токен не подходит.")
    elif isinstance(result, str) and result.startswith("exception_"):
        await msg.edit_text(f"❌ Проблема со связью: {result.split('_')[1]}")
    elif result:
        try:
            await message.answer_photo(
                photo=BufferedInputFile(result, filename="gen.jpg"),
                caption=f"✨ <b>Результат:</b> {prompt}"
            )
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ Ошибка отправки фото: {e}")
    else:
        await msg.edit_text("❌ Неизвестная ошибка. Попробуй позже.")

# --- ОСТАЛЬНЫЕ КОМАНДЫ (БАЗА) ---
@base_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("🏠 Бот обновлен! Пытаемся запустить Hugging Face.\n\nКоманда: /gen [текст]")

@base_router.message(Command("rating"))
async def cmd_rating(message: Message):
    conn = await get_db_connection()
    rows = await conn.fetch('SELECT name, score FROM reputation ORDER BY score DESC')
    await conn.close()
    if not rows: return await message.answer("🏆 Рейтинг пока пуст.")
    res = "<b>🏆 Рейтинг семьи:</b>\n" + "\n".join([f"{r['name']}: {r['score']}" for r in rows])
    await message.answer(res)
