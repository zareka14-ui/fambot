from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.utils.markdown import hbold

# Создаем роутер
base_router = Router()

@base_router.message(CommandStart())
async def command_start_handler(message: types.Message):
    """
    Этот хэндлер срабатывает на команду /start
    """
    await message.answer(f"Привет, {hbold(message.from_user.full_name)}! \nЯ готов к работе в семейном чате! 🏠")

@base_router.message()
async def echo_handler(message: types.Message):
    """
    Временный эхо-хэндлер (потом удалим).
    Повторяет все, что не является командой.
    """
    try:
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        await message.answer("Хорошая попытка, но я не могу это скопировать 🙂")