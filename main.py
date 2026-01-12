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
PORT = int(os.getenv("PORT", 8080)) # Порт для Render

PAYMENT_INFO = """
Перевод по номеру телефона:
+7 912 459 1439 (СберБанк и Тбанк)
Получатель: Екатерина Б.

Сумма депозита: 2999 руб.
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

# --- ХЭНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "✨ **Регистрация на мистерию «Сила Рода: Сталь, Соль и Огонь»**\n\n"
        "Это не просто мастер-класс, а сакральный обряд очищения и возвращения силы. "
        "Чтобы мы подготовили для вас индивидуальный набор артефактов, пожалуйста, ответьте на несколько вопросов."
    )
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Начать регистрацию")]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=kb)

@dp.message(F.text == "Начать регистрацию")
async def start_form(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, напишите ваше **ФИО** полностью.", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Напишите ваш **контакт для связи** (Ник в Telegram или номер WhatsApp).")
    await state.set_state(Registration.waiting_for_contact)

@dp.message(Registration.waiting_for_contact)
async def process_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await message.answer("Есть ли у вас **аллергия** (на масла, травы, металлы)? Если нет — напишите «Нет».")
    await state.set_state(Registration.waiting_for_allergies)

@dp.message(Registration.waiting_for_allergies)
async def process_allergies(message: types.Message, state: FSMContext):
    await state.update_data(allergies=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Принимаю условия оферты", url=OFFER_LINK)],
                                               [InlineKeyboardButton(text="📝 Я подтверждаю согласие", callback_data="offer_accepted")]])
    await message.answer(f"Пожалуйста, ознакомьтесь с офертой и подтвердите согласие кнопкой ниже.", reply_markup=kb)
    await state.set_state(Registration.waiting_for_offer_agreement)

@dp.callback_query(F.data == "offer_accepted", Registration.waiting_for_offer_agreement)
async def process_offer(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    booking_text = (
        "Принято! Твой запрос услышан полем.\n"
        "Для бронирования места (депозит 2999 руб) используйте реквизиты:\n"
        f"{PAYMENT_INFO}\n\n"
        "📎 **Отправьте чек об оплате (скриншот) сюда.**"
    )
    await callback.message.edit_text("✅ Оферта принята.")
    await callback.message.answer(booking_text, parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_payment_proof)

@dp.message(Registration.waiting_for_payment_proof, F.photo | F.document)
async def process_payment_proof(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    admin_report = (
        "🆕 **НОВАЯ ЗАЯВКА!**\n\n"
        f"👤 **ФИО:** {user_data['name']}\n"
        f"📞 **Связь:** {user_data['contact']}\n"
        f"⚠️ **Аллергии:** {user_data['allergies']}\n"
        f"🔗 **Профиль:** {message.from_user.mention_html()}"
    )
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, admin_report, parse_mode="HTML")
            await message.copy_to(ADMIN_ID) # Копируем чек админу
        except Exception as e:
            logging.error(f"Ошибка отправки админу: {e}")
    
    await message.answer("Благодарим! Ваша бронь принята. Мы скоро свяжемся с вами. Готовьте удобную одежду! 🔥")
    await state.clear()

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
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
    # Запускаем бота и сервер одновременно
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
