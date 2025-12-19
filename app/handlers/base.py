import random
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message

base_router = Router()

# Список покупок (в оперативной памяти)
shopping_list = []

# --- 1. КУБИКИ И ИГРЫ TELEGRAM ---
@base_router.message(Command("dice"))
async def play_dice(message: Message):
    await message.answer_dice(emoji="🎲")

@base_router.message(Command("darts"))
async def play_darts(message: Message):
    await message.answer_dice(emoji="🎯")

@base_router.message(Command("basketball"))
async def play_basketball(message: Message):
    await message.answer_dice(emoji="🏀")

# --- 2. КТО СЕГОДНЯ...? ---
@base_router.message(Command("who"))
async def who_is_it(message: Message):
    tasks = [
        "идет за хлебом 🥖", "моет посуду 🍽", "выбирает фильм 🎬",
        "заваривает чай ☕️", "отдыхает 😎", "выносит мусор 🗑"
    ]
    task = random.choice(tasks)
    await message.answer(f"Сегодня <b>{message.from_user.first_name}</b> {task}!")

# --- 3. КАМЕНЬ, НОЖНИЦЫ, БУМАГА ---
@base_router.message(Command("rps", "кнб"))
async def rps_game(message: Message):
    args = message.text.split()
    choices = {"камень": "🪨", "ножницы": "✂️", "бумага": "📄"}
    
    if len(args) < 2:
        await message.reply("Напиши: <code>/кнб камень</code> (ножницы или бумага)")
        return

    user_choice = args[1].lower()
    if user_choice in choices:
        bot_choice = random.choice(list(choices.keys()))
        win_map = {"камень": "ножницы", "ножницы": "бумага", "бумага": "камень"}
        
        if user_choice == bot_choice:
            res = "Ничья! 🤝"
        elif win_map[user_choice] == bot_choice:
            res = "Ты победил! 🎉"
        else:
            res = "Я победил! 😎"
        
        await message.reply(f"Твой: {choices[user_choice]}\nМой: {choices[bot_choice]}\n\n{res}")
    else:
        await message.reply("Выбери: камень, ножницы или бумага!")

# --- 4. СПИСОК ПОКУПОК ---
@base_router.message(Command("купить"))
async def add_to_list(message: Message):
    item = message.text.replace("/купить", "").strip()
    if item:
        shopping_list.append(item)
        await message.answer(f"✅ Добавлено: <b>{item}</b>")
    else:
        await message.answer("Пример: <code>/купить молоко</code>")

@base_router.message(Command("список"))
async def show_list(message: Message):
    if not shopping_list:
        await message.answer("Список пуст! ✨")
    else:
        items = "\n".join([f"{i}. {item}" for i, item in enumerate(shopping_list, 1)])
        await message.answer(f"<b>🛒 Нужно купить:</b>\n\n{items}")

@base_router.message(Command("купил"))
async def clear_list(message: Message):
    global shopping_list
    shopping_list = []
    await message.answer("🧹 Список очищен!")

# --- 5. ОПРОСЫ И ПОМОЩЬ ---
@base_router.message(Command("ужин"))
async def dinner_poll(message: Message):
    await message.answer_poll(
        question="Что на ужин? 🍕",
        options=["Пицца/Суши", "Домашнее", "В кафе", "Холодильник"],
        is_anonymous=False
    )

@base_router.message(Command("help_fun"))
async def fun_help(message: Message):
    await message.answer(
        "<b>Команды:</b>\n/dice, /darts, /who\n"
        "/кнб камень — игра\n/купить, /список, /купил\n/ужин — опрос"
    )
