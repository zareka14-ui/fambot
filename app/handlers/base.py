import os
import random
import asyncio
import asyncpg
import logging
from datetime import datetime
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

base_router = Router()
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# --- РУССКАЯ МОТИВАЦИЯ ---
async def get_russian_quote():
    quotes = [
        "Семья — это не главное. Семья — это всё. 🏠",
        "Счастлив тот, кто счастлив у себя дома. ✨",
        "Успех — это сумма маленьких усилий, повторяющихся изо дня в день. 💪",
        "Единственный способ сделать выдающуюся работу — искренне любить то, что делаешь. ❤️",
        "Препятствия — это те страшные вещи, которые вы видите, когда отводите взгляд от цели. 🎯",
        "Семья — это маленький мир, созданный любовью. 🌍",
        "Величайшее в жизни счастье — это уверенность в том, что тебя любят. 🥰",
        "Дом — это не место, а состояние души. 🗝"
    ]
    return random.choice(quotes)

async def send_motivation_to_chat(bot: Bot, chat_id: int):
    quote = await get_russian_quote()
    # Берем фото природы/дома
    photo_url = f"https://picsum.photos/800/600?nature,house&sig={random.randint(1, 1000)}"
    try:
        await bot.send_photo(
            chat_id, 
            photo_url, 
            caption=f"<b>Заряд бодрости на сегодня! ☀️</b>\n\n{quote}",
            parse_mode="HTML"
        )
    except Exception as e:
        await bot.send_message(chat_id, f"<b>Доброе утро! ☀️</b>\n\n{quote}", parse_mode="HTML")

# --- ОБРАБОТЧИК /START И КНОПОК ---
@base_router.message(Command("start"))
async def cmd_start(message: Message):
    # Создаем кнопки правильно
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Мотивация", callback_data="get_motivation")],
        [
            InlineKeyboardButton(text="🏆 Рейтинг", callback_data="rating_data"),
            InlineKeyboardButton(text="📜 Справка", callback_data="help_data")
        ]
    ])
    
    await message.answer(
        f"<b>Привет, {message.from_user.first_name}! 👋</b>\n\nЯ твой Домовой. Помогаю по дому и слежу за уютом.\n"
        "Нажми на кнопки ниже или используй меню команд.",
        reply_markup=keyboard
    )

# --- ОБРАБОТКА НАЖАТИЙ НА КНОПКИ ---
@base_router.callback_query(F.data == "get_motivation")
async def cb_motivation(callback: types.CallbackQuery, bot: Bot):
    await send_motivation_to_chat(bot, callback.message.chat.id)
    await callback.answer()

@base_router.callback_query(F.data == "help_data")
async def cb_help(callback: types.CallbackQuery):
    await help_command(callback.message)
    await callback.answer()

@base_router.callback_query(F.data == "rating_data")
async def cb_rating(callback: types.CallbackQuery):
    await cmd_rating(callback.message)
    await callback.answer()

# --- ВСЕ ОСТАЛЬНЫЕ КОМАНДЫ (motivation, rating, buy и т.д.) ---
@base_router.message(Command("motivation"))
async def manual_motivation(message: Message, bot: Bot):
    await send_motivation_to_chat(bot, message.chat.id)

# ... (остальной код команд /who, /rating, /buy остается без изменений) ...
