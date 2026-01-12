import asyncio
import logging
import os
import sys
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN") 
ADMIN_ID = os.getenv("ADMIN_ID") 
PORT = int(os.getenv("PORT", 8080))

OFFER_LINK = "https://disk.yandex.ru/i/965-_UGNIPkaaQ"

class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_allergies = State()
    confirm_data = State() # Новый этап проверки
    waiting_for_payment_proof = State()

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_start_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Начать регистрацию")]],
        resize_keyboard=True, one_time_keyboard=True
    )

def get_progress(step):
    """Визуальный индикатор прогресса"""
    steps = ["⬜", "⬜", "⬜", "⬜"]
    for i in range(step):
        steps[i] = "✅"
    return "".join(steps)

# --- ХЭНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "✨ **МИСТЕРИЯ «СИЛА РОДА»**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Добро пожаловать в сакральное пространство. Чтобы подготовить ваш "
        "индивидуальный набор артефактов, нам нужно познакомиться.\n\n"
        "Нажмите кнопку ниже, чтобы начать."
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_start_kb())

@dp.message(F.text == "🚀 Начать регистрацию")
async def start_form(message: types.Message, state: FSMContext):
    await message.answer(
        f"{get_progress(0)}\n**Шаг 1:** Введите ваше **ФИО** полностью:",
        reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown"
    )
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        f"{get_progress(1)}\n**Шаг 2:** Напишите ваш **номер телефона**:\n"
        "_(Или ник в Telegram)_", parse_mode="Markdown"
    )
    await state.set_state(Registration.waiting_for_contact)

@dp.message(Registration.waiting_for_contact, F.text)
async def process_contact(message: types.Message, state: FSMContext):
    phone_digits = re.sub(r'\D', '', message.text)
    if 10 <= len(phone_digits) <= 15 or message.text.startswith('@'):
        await state.update_data(contact=message.text)
        await message.answer(
            f"{get_progress(2)}\n**Шаг 3:** Есть ли у вас **аллергия**?\n"
            "_(Масла, травы, металлы). Если нет — напишите «Нет»._", parse_mode="Markdown"
        )
        await state.set_state(Registration.waiting_for_allergies)
    else:
        await message.answer("⚠️ Пожалуйста, введите корректный номер или @username.")

@dp.message(Registration.waiting_for_allergies, F.text)
async def process_allergies(message: types.Message, state: FSMContext):
    await state.update_data(allergies=message.text)
    data = await state.get_data()
    
    # ЭТАП ПОДТВЕРЖДЕНИЯ (КРАСОТА И УДОБСТВО)
    summary = (
        f"{get_progress(3)}\n**ПРОВЕРЬТЕ ВАШИ ДАННЫЕ:**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 **ФИО:** {data['name']}\n"
        f"📞 **Связь:** {data['contact']}\n"
        f"⚠️ **Аллергии:** {data['allergies']}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Если всё верно — подтвердите оферту."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Читать оферту", url=OFFER_LINK)],
        [InlineKeyboardButton(text="✅ Все верно, согласен", callback_data="confirm_ok")],
        [InlineKeyboardButton(text="❌ Заполнить заново", callback_data="restart")]
    ])
    await message.answer(summary, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(Registration.confirm_data)

@dp.callback_query(F.data == "restart")
async def restart_form(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Сброс данных...")
    await start_form(callback.message, state)

@dp.callback_query(F.data == "confirm_ok", Registration.confirm_data)
async def process_confirm(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    pay_text = (
        "✅ **ДАННЫЕ ПРИНЯТЫ**\n\n"
        "Для бронирования места переведите депозит **2999 руб.**\n\n"
        "📌 **Реквизиты (нажмите, чтобы скопировать):**\n"
        "`+79124591439` (Сбер / Т-Банк)\n"
        "👤 Получатель: Екатерина Б.\n\n"
        "📎 **После оплаты пришлите скриншот чека сюда.**"
    )
    await callback.message.edit_text(pay_text, parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_payment_proof)

@dp.message(Registration.waiting_for_payment_proof, F.photo | F.document)
async def process_payment_proof(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    admin_report = (
        "🔥 **НОВАЯ ЗАЯВКА НА МИСТЕРИЮ**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 **ФИО:** {user_data.get('name')}\n"
        f"📞 **Связь:** {user_data.get('contact')}\n"
        f"⚠️ **Аллергии:** {user_data.get('allergies')}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"🔗 Профиль: {message.from_user.mention_html()}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, admin_report, parse_mode="HTML")
            await message.copy_to(ADMIN_ID)
        except Exception as e:
            logging.error(f"Ошибка админа: {e}")
    
    await message.answer(
        "✨ **БЛАГОДАРИМ!**\n\nВаша бронь принята. Мы свяжемся с вами в ближайшее время для подтверждения. "
        "До встречи на мистерии!", 
        reply_markup=get_start_kb(), parse_mode="Markdown"
    )
    await state.clear()

# --- ВЕБ-СЕРВЕР ---
async def handle(request):
    return web.Response(text="Bot is alive")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

# --- ЗАПУСК ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands([types.BotCommand(command="start", description="Запустить регистрацию")])
    await asyncio.gather(dp.start_polling(bot), start_web_server())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
