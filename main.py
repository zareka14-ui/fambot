import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
# Если запускаешь локально, используй .env, на Render пропиши переменные в Environment
TOKEN = os.getenv("BOT_TOKEN") 
# ID админа, куда будут приходить заполненные анкеты (узнать свой ID можно у бота @userinfobot)
ADMIN_ID = os.getenv("ADMIN_ID") 

# Реквизиты для оплаты
PAYMENT_INFO = """
Перевод по номеру телефона:
+7 912 459 1439 (СберБанк и Тбанк)
Получатель: Екатерина Б.

Сумма депозита: 2999 руб.
"""

# Ссылка на оферту (замени на свою ссылку на Google Doc или Teletype)
OFFER_LINK = "https://disk.yandex.ru/i/965-_UGNIPkaaQ"

# --- СОСТОЯНИЯ (ЭТАПЫ АНКЕТЫ) ---
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_allergies = State()
    waiting_for_offer_agreement = State()
    waiting_for_payment_proof = State()

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- ХЭНДЛЕРЫ (ОБРАБОТЧИКИ) ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Начало диалога. Приветствие."""
    # Сбрасываем состояние, если пользователь начал заново
    await state.clear()
    
    welcome_text = (
        "✨ **Регистрация на мистерию «Сила Рода: Сталь, Соль и Огонь»**\n\n"
        "Это не просто мастер-класс, а сакральный обряд очищения и возвращения силы. "
        "Чтобы мы подготовили для вас индивидуальный набор артефактов, пожалуйста, ответьте на несколько вопросов."
    )
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Начать регистрацию")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=kb)

@dp.message(F.text == "Начать регистрацию")
async def start_form(message: types.Message, state: FSMContext):
    """Шаг 1: Спрашиваем ФИО"""
    await message.answer("Пожалуйста, напишите ваше **ФИО** полностью.", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    """Шаг 2: Сохраняем имя, спрашиваем контакт"""
    await state.update_data(name=message.text)
    
    await message.answer(
        "Напишите ваш **контакт для связи** (Ник в Telegram или номер WhatsApp).\n"
        "Это важно для добавления в закрытый чат участников."
    )
    await state.set_state(Registration.waiting_for_contact)

@dp.message(Registration.waiting_for_contact)
async def process_contact(message: types.Message, state: FSMContext):
    """Шаг 3: Сохраняем контакт, спрашиваем про аллергию"""
    await state.update_data(contact=message.text)
    
    await message.answer(
        "Есть ли у вас **аллергия** (на масла, травы, металлы, пищевая)?\n"
        "Если нет — напишите «Нет».\n"
        "Если есть — укажите подробно. Мы будем использовать эфирные масла и соль."
    )
    await state.set_state(Registration.waiting_for_allergies)

@dp.message(Registration.waiting_for_allergies)
async def process_allergies(message: types.Message, state: FSMContext):
    """Шаг 4: Сохраняем аллергии, предлагаем оферту"""
    await state.update_data(allergies=message.text)
    
    offer_text = (
        f"Перед оплатой необходимо принять условия оферты: {OFFER_LINK}\n\n"
        "Нажимая кнопку «Принимаю», вы соглашаетесь с условиями договора и правилами проведения мероприятия."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю условия оферты", callback_data="offer_accepted")]
    ])
    
    await message.answer(offer_text, reply_markup=kb)
    await state.set_state(Registration.waiting_for_offer_agreement)

@dp.callback_query(F.data == "offer_accepted", Registration.waiting_for_offer_agreement)
async def process_offer(callback: types.CallbackQuery, state: FSMContext):
    """Шаг 5: Оферта принята. Выдаем реквизиты и просим депозит"""
    await callback.answer() # Убираем часики загрузки у кнопки
    
    booking_text = (
        "Принято! Твой запрос услышан полем.\n\n"
        "Для бронирования места в круге (их всего 15) необходимо внести **депозит в размере 2999 руб.**\n\n"
        "Эта сумма идет на закупку твоего личного набора: металлического артефакта-якоря, заговоренной соли и масел. "
        "Оставшаяся сумма оплачивается в день мистерии.\n\n"
        f"{PAYMENT_INFO}\n\n"
        "📎 **Пожалуйста, отправьте чек об оплате (скриншот или файл) в этот чат.**"
    )
    
    await callback.message.edit_text("✅ Оферта принята.")
    await callback.message.answer(booking_text, parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_payment_proof)

@dp.message(Registration.waiting_for_payment_proof, F.photo | F.document)
async def process_payment_proof(message: types.Message, state: FSMContext):
    """Шаг 6: Получаем чек, отправляем данные Админу, шлем Памятку пользователю"""
    
    user_data = await state.get_data()
    
    # --- ОТПРАВКА АДМИНУ ---
    # Формируем отчет для админа
    admin_report = (
        "🆕 **НОВАЯ РЕГИСТРАЦИЯ!**\n\n"
        f"👤 **ФИО:** {user_data['name']}\n"
        f"📞 **Связь:** {user_data['contact']}\n"
        f"⚠️ **Аллергии:** {user_data['allergies']}\n"
        f"✅ **Оферта:** Принята\n"
        f"🔗 **Профиль:** {message.from_user.mention_html()}\n"
    )
    
    if ADMIN_ID:
        # Отправляем текст анкеты админу
        await bot.send_message(ADMIN_ID, admin_report, parse_mode="HTML")
        # Пересылаем чек (фото или документ)
        await message.forward(ADMIN_ID)
    else:
        logging.warning("ADMIN_ID не указан! Анкета не отправлена админу.")

    # --- ОТПРАВКА ПОЛЬЗОВАТЕЛЮ ---
    memo_text = (
        "Благодарим! Ваша бронь принята, чек отправлен администратору на проверку. "
        "Мы свяжемся с вами в ближайшее время для подтверждения.\n\n"
        "📜 **ПАМЯТКА УЧАСТНИКУ**\n"
        "__________________________\n"
        "👕 **Одежда:** Удобная, не стесняющая движений (лучше светлых тонов или из натуральных тканей). "
        "Мы будем стоять босиком на соли.\n\n"
        "До встречи в круге! 🔥"
    )
    
    await message.answer(memo_text, parse_mode="Markdown")
    await state.clear() # Завершаем диалог

@dp.message(Registration.waiting_for_payment_proof)
async def incorrect_payment_type(message: types.Message):
    """Если пользователь на этапе оплаты прислал текст вместо картинки"""
    await message.answer("Пожалуйста, прикрепите **изображение чека** или PDF файл.")

# --- ЗАПУСК ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
