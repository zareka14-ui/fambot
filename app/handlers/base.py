import os
import random
import asyncio
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

base_router = Router()

# Вспомогательная функция для мотивации (теперь доступна в base_router)
async def get_motivation(message: Message):
    quotes = [
        "Семья — это не главное. Семья — это всё.",
        "Счастлив тот, кто счастлив у себя дома.",
        "Семья — это маленький мир, созданный любовью."
    ]
    quote = random.choice(quotes)
    # Используем проверенную уютную картинку из интернета, так как генерация требует API
    photo_url = "https://images.unsplash.com/photo-1511895426328-dc8714191300?q=80&w=1000"
    
    await message.answer_photo(
        photo=photo_url,
        caption=f"<b>Мотивация для семьи 🏠</b>\n\n<i>{quote}</i>",
        parse_mode="HTML"
    )

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", web_app=WebAppInfo(url="https://prizes.gamee.com/"))],
        [
            InlineKeyboardButton(text="📜 Справка", callback_data="help_display"),
            InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_display")
        ]
    ])
    await message.answer(
        f"<b>Привет, {message.from_user.first_name}! 👋</b>\nЯ ваш семейный помощник.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@base_router.message(Command("motivation"))
async def cmd_motivation(message: Message):
    await get_motivation(message)

@base_router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "<b>🏠 Команды:</b>\n"
        "/motivation - открытка\n"
        "/buy [товар] - купить\n"
        "/list - список покупок\n"
        "/rating - рейтинг семьи"
    )
    await message.answer(text, parse_mode="HTML")

# Обработка кнопок
@base_router.callback_query(F.data == "help_display")
async def help_callback(callback: types.CallbackQuery):
    await cmd_help(callback.message)
    await callback.answer()

@base_router.callback_query(F.data == "rating_display")
async def rating_callback(callback: types.CallbackQuery):
    # Здесь должна быть ваша логика рейтинга
    await callback.message.answer("Рейтинг пока в разработке 📈")
    await callback.answer()
