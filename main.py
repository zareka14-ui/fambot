import asyncio
import logging
import os
import sys
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

PAYMENT_INFO = """
**Перевод по номеру телефона:**
`+79124591439` (СберБанк и Тбанк)
Получатель: Екатерина Б.

Сумма депозита: **2999 руб.**
"""

OFFER_LINK = "https://disk.yandex.ru/i/965-_UGNIPkaaQ"

class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_allergies = State()
    waiting_for_offer_agreement = State()
    waiting_for_payment_proof = State()

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ВСПОМОГАТЕЛЬНЫЕ КЛАВИАТУРЫ ---
def get_start_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Начать регистрацию")]],
        resize_keyboard=True, one_time_keyboard=True
    )

# --- ХЭНДЛЕРЫ ЗАЩИТЫ ---

# 1. Сброс состояния при /start в любой момент
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "✨ **Регистрация на мистерию «Сила Рода: Сталь, Соль и Огонь»**\n\n"
        "Это не просто мастер-класс, а сакральный обряд очищения. "
        "Чтобы мы подготовили ваш набор артефактов, ответьте на вопросы."
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_start_kb())

# 2. Начало регистрации
@dp.message(F.text == "Начать регистрацию")
async def start_form(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, напишите ваше **ФИО** полностью.", 
                         reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_name)

# 3. Обработка ФИО (+ защита от не-текста)
@dp.message(Registration.waiting_for_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Напишите ваш **контакт для связи** (номер телефона).", parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_contact)

@dp.message(Registration.waiting_for_name)
async def warn_name(message: types.Message):
    await message.answer("⚠️ Пожалуйста, пришлите ваше ФИО текстом.")

# 4. Обработка контакта (+ защита)
@dp.message(Registration.waiting_for_contact, F.text)
async def process_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await message.answer("Есть ли у вас **аллергия** (на масла, травы, металлы)? Если нет — напишите «Нет».", parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_allergies)

@dp.message(Registration.waiting_for_contact)
async def warn_contact(message: types.Message):
    await message.answer("⚠️ Пожалуйста, введите номер телефона или ник текстом.")

# 5. Обработка аллергий
@dp.message(Registration.waiting_for_allergies, F.text)
async def process_allergies(message: types.Message, state: FSMContext):
    await state.update_data(allergies=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Условия оферты", url=OFFER_LINK)],
        [InlineKeyboardButton(text="📝 Я подтверждаю согласие", callback_data="offer_accepted")]
    ])
    await message.answer("Пожалуйста, ознакомьтесь с офертой и подтвердите согласие кнопкой ниже.", reply_markup=kb)
    await state.set_state(Registration.waiting_for_offer_agreement)

# 6. Защита на этапе оферты (если пользователь пишет вместо нажатия кнопки)
@dp.message(Registration.waiting_for_offer_agreement)
async def warn_offer(message: types.Message):
    await message.answer("⚠️ Чтобы продолжить, нужно нажать на кнопку «Я подтверждаю согласие» выше.")

@dp.callback_query(F.data == "offer_accepted", Registration.waiting_for_offer_agreement)
async def process_offer(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    booking_text = (
        "Принято! \n\n"
        "Для бронирования места используйте реквизиты:\n"
        f"{PAYMENT_INFO}\n\n"
        "📎 **Отправьте чек об оплате (скриншот или PDF) сюда.**"
    )
    await callback.message.edit_text("✅ Оферта принята.")
    await callback.message.answer(booking_text, parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_payment_proof)

# 7. Обработка чека (только фото или документ)
@dp.message(Registration.waiting_for_payment_proof, F.photo | F.document)
async def process_payment_proof(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    admin_report = (
        "🆕 **НОВАЯ ЗАЯВКА!**\n\n"
        f"👤 **ФИО:** {user_data.get('name')}\n"
        f"📞 **Связь:** {user_data.get('contact')}\n"
        f"⚠️ **Аллергии:** {user_data.get('allergies')}\n"
        f"🔗 **Профиль:** {message.from_user.mention_html()}"
    )
    
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, admin_report, parse_mode="HTML")
            await message.copy_to(ADMIN_ID)
        except Exception as e:
            logging.error(f"Ошибка отправки админу: {e}")
    
    await message.answer("Благодарим! Ваша бронь принята. Мы скоро свяжемся с вами. 🔥", reply_markup=get_start_kb())
    await state.clear()

@dp.message(Registration.waiting_for_payment_proof)
async def warn_payment(message: types.Message):
    await message.answer("⚠️ Пожалуйста, пришлите подтверждение оплаты в виде **фотографии (скриншота)** или **файла**.")

# 8. Глобальный эхо-обработчик (для всех сообщений "не в тему")
@dp.message()
async def global_echo(message: types.Message):
    await message.answer("Я вас не совсем понял. Чтобы начать сначала, нажмите /start или используйте кнопки меню.")

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
    # Удаляем вебхуки и ставим кнопку "Меню" в интерфейс
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Начать регистрацию")
    ])
    
    # Запускаем бота и сервер
    logging.info("Starting bot...")
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
