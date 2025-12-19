import random
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message

base_router = Router()

# --- 1. КУБИКИ И ДРОТИКИ ---
@base_router.message(Command("dice"))
async def play_dice(message: Message):
    """Бросает игральный кубик"""
    await message.answer_dice(emoji="🎲")

@base_router.message(Command("darts"))
async def play_darts(message: Message):
    """Игра в дротики"""
    await message.answer_dice(emoji="🎯")

@base_router.message(Command("basketball"))
async def play_basketball(message: Message):
    """Забросит ли мяч в кольцо?"""
    await message.answer_dice(emoji="🏀")


# --- 2. РАНДОМ ДНЯ (КТО СЕГОДНЯ...?) ---
@base_router.message(Command("who"))
async def who_is_it(message: Message):
    """Выбирает случайное дело для того, кто вызвал команду"""
    tasks = [
        "идет за хлебом 🥖",
        "моет посуду 🍽",
        "выбирает фильм на вечер 🎬",
        "заваривает всем чай ☕️",
        "сегодня отдыхает и ничего не делает 😎",
        "выносит мусор 🗑",
        "рассказывает смешную историю 🤡"
    ]
    task = random.choice(tasks)
    # Используем mention или first_name для обращения
    user_name = message.from_user.first_name
    await message.answer(f"По решению магического кубика, сегодня <b>{user_name}</b> {task}!")


# --- 3. КАМЕНЬ, НОЖНИЦЫ, БУМАГА ---
@base_router.message(Command("rps"))
async def rock_paper_scissors(message: Message):
    """Простая игра против бота"""
    options = ["Камень 🪨", "Ножницы ✂️", "Бумага 📄"]
    bot_choice = random.choice(options)
    
    # Можно добавить логику проверки текста после команды, если пользователь ввел свой вариант
    # Но для начала сделаем просто забавный ответ
    await message.reply(
        f"Мой выбор: <b>{bot_choice}</b>!\n"
        f"Если у тебя сильнее — ты победил! 🏆"
    )

# Можно добавить хелп, чтобы семья знала команды
@base_router.message(Command("help_fun"))
async def fun_help(message: Message):
    help_text = (
        "<b>Развлекательные команды:</b>\n"
        "/dice — Бросить кубик 🎲\n"
        "/darts — Дротики 🎯\n"
        "/basketball — Баскетбол 🏀\n"
        "/who — Узнать, кто сегодня что делает 🧐\n"
        "/rps — Камень, ножницы, бумага ✂️"
    )
    await message.answer(help_text)
