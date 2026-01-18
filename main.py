import asyncio
import logging
import os
import sys
import datetime
import io
import json
from collections import defaultdict

# Библиотеки Google
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Aiogram
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardRemove
)
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN") 
ADMIN_ID = os.getenv("ADMIN_ID") 
PORT = int(os.getenv("PORT", 8080))

OFFER_LINK = "https://disk.yandex.ru/i/965-_UGNIPkaaQ"
MAX_PEOPLE_PER_SLOT = 15

# --- НАСТРОЙКИ GOOGLE ---
SHEET_NAME = "Запись на Мистерию"
DRIVE_FOLDER_ID = "1aPzxYWdh085ZjQnr2KXs3O_HMCCWpfhn" 

# Хранилище занятых мест (сбрасывается при перезагрузке на Render)
BOOKED_SLOTS = defaultdict(int)

class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_allergies = State()
    confirm_data = State()
    waiting_for_payment_proof = State()

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ДАННЫЕ МЕРОПРИЯТИЙ ---
DATES_CONFIG = {
    "📅 21 янв (ср) | 📍 Иглино": "21 января (ср) - Иглино",
    "📅 23 янв (пт) | 📍 Бакалинская 25": "23 января (пт) - Бакалинская 25",
    "📅 25 янв (вс) | 📍 Бакалинская 25": "25 января (вс) - Бакалинская 25"
}
TIMES_CONFIG = ["🕙 10:00", "🕖 19:00"]

# --- ФУНКЦИИ GOOGLE (АВТОРИЗАЦИЯ ЧЕРЕЗ ПЕРЕМЕННУЮ ОКРУЖЕНИЯ) ---

async def upload_to_drive_and_save_row(data, photo_file_id):
    """Загрузка файла и запись в таблицу с авторизацией через словарь"""
    try:
        # 1. Скачиваем фото из Телеграм в память
        file_info = await bot.get_file(photo_file_id)
        file_content_io = await bot.download_file(file_info.file_path)
        content_bytes = file_content_io.read()

        def _sync_logic(content):
            # Извлекаем ключ из переменной окружения Render
            env_key = os.getenv("GOOGLE_JSON_KEY")
            if not env_key:
                raise ValueError("GOOGLE_JSON_KEY not found in environment!")
            
            key_data = json.loads(env_key)
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            
            # Авторизация через словарь данных
            creds = ServiceAccountCredentials.from_json_key_dict(key_data, scope)
            
            # 1. Загрузка на Google Drive
            drive_service = build('drive', 'v3', credentials=creds, cache_discovery=False)
            file_metadata = {
                'name': f"Чек_{data['name']}_{datetime.datetime.now().strftime('%d_%m_%H%M')}.jpg",
                'parents': [DRIVE_FOLDER_ID]
            }
            media = MediaIoBaseUpload(io.BytesIO(content), mimetype='image/jpeg', resumable=True)
            drive_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
            
            # 2. Запись в Google Таблицу
            client = gspread.authorize(creds)
            sheet = client.open(SHEET_NAME).sheet1
            row = [
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                data.get('name'), data.get('contact'),
                data.get('selected_date'), data.get('selected_time'),
                data.get('allergies'), drive_file.get('webViewLink')
            ]
            sheet.append_row(row)
            return True

        return await asyncio.to_thread(_sync_logic, content_bytes)
    except Exception as e:
        logging.error(f"Ошибка Google Services: {e}")
        return False

# --- КЛАВИАТУРЫ ---

def get_start_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚀 Начать регистрацию")]], resize_keyboard=True)

def get_dates_kb():
    buttons = [[KeyboardButton(text=d)] for d in DATES_CONFIG.keys()]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_times_kb():
    buttons = [[KeyboardButton(text=t)] for t in TIMES_CONFIG]
    buttons.append([KeyboardButton(text="⬅️ Назад к датам")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_progress(step):
    total = 6
    steps = ["⬜"] * total
    for i in range(step): steps[i] = "✅"
    return "".join(steps)

# --- ХЭНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✨ **МИСТЕРИЯ «СТАЛЬ • СОЛЬ • ОГОНЬ • ШАМАН и МАГИЯ РОДА»**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Добро пожаловать. Для подготовки индивидуальных артефактов нам нужно познакомиться.",
        parse_mode="Markdown", reply_markup=get_start_kb()
    )

@dp.message(F.text == "🚀 Начать регистрацию")
async def start_form(message: types.Message, state: FSMContext):
    await message.answer(f"{get_progress(0)}\n**Шаг 1:** Введите ваше **ФИО**:", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(f"{get_progress(1)}\n**Шаг 2:** Ваш **номер телефона** или @username:", parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_contact)

@dp.message(Registration.waiting_for_contact, F.text)
async def process_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    # ПЕРЕХОД К ДАТАМ (ИСПРАВЛЕНО)
    await message.answer(f"{get_progress(2)}\n**Шаг 3:** Выберите **дату и место**:", reply_markup=get_dates_kb(), parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_date)

@dp.message(Registration.waiting_for_date, F.text)
async def process_date(message: types.Message, state: FSMContext):
    if message.text not in DATES_CONFIG:
        await message.answer("Пожалуйста, выберите вариант из кнопок.")
        return
    await state.update_data(selected_date=message.text)
    # ПЕРЕХОД К ВРЕМЕНИ (ИСПРАВЛЕНО)
    await message.answer(f"{get_progress(3)}\n**Шаг 4:** Выберите **время**:", reply_markup=get_times_kb(), parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_time)

@dp.message(Registration.waiting_for_time, F.text)
async def process_time(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад к датам":
        await message.answer("Выберите дату:", reply_markup=get_dates_kb())
        await state.set_state(Registration.waiting_for_date)
        return
    if message.text not in TIMES_CONFIG: return
    
    data = await state.get_data()
    slot_id = f"{data['selected_date']}_{message.text}"
    if BOOKED_SLOTS[slot_id] >= MAX_PEOPLE_PER_SLOT:
        await message.answer("😔 Мест на это время нет. Выберите другое.")
        return

    await state.update_data(selected_time=message.text)
    # ПЕРЕХОД К АЛЛЕРГИИ (ИСПРАВЛЕНО)
    await message.answer(f"{get_progress(4)}\n**Шаг 5:** Есть ли **аллергия**? (Если нет — напишите «Нет»)", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_allergies)

@dp.message(Registration.waiting_for_allergies, F.text)
async def process_allergies(message: types.Message, state: FSMContext):
    await state.update_data(allergies=message.text)
    data = await state.get_data()
    summary = (
        f"{get_progress(5)}\n**ПРОВЕРЬТЕ ДАННЫЕ:**\n"
        f"👤 {data['name']}\n📞 {data['contact']}\n🗓 {data['selected_date']}\n⏰ {data['selected_time']}\n⚠️ {data['allergies']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Оферта", url=OFFER_LINK)],
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_ok")],
        [InlineKeyboardButton(text="❌ Заново", callback_data="restart")]
    ])
    await message.answer(summary, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(Registration.confirm_data)

@dp.callback_query(F.data == "restart")
async def restart_form(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_form(callback.message, state)

@dp.callback_query(F.data == "confirm_ok")
async def process_confirm(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    pay_text = (
        "✅ **ДАННЫЕ ПРИНЯТЫ**\n\nПришлите скриншот чека об оплате депозита (**2999 р.**)\n"
        "Реквизиты: `+79124591439` (Сбер/Т-Банк, Екатерина Б.)"
    )
    await callback.message.edit_text(pay_text, parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_payment_proof)

@dp.message(Registration.waiting_for_payment_proof, F.photo)
async def process_payment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    wait_msg = await message.answer("⌛ Сохраняю в облако...")
    
    success = await upload_to_drive_and_save_row(data, message.photo[-1].file_id)
    
    if success:
        slot_id = f"{data['selected_date']}_{data['selected_time']}"
        BOOKED_SLOTS[slot_id] += 1
        if ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"🔥 **ОПЛАТА**\n{data['name']}\n{data['selected_date']} {data['selected_time']}")
            await message.copy_to(ADMIN_ID)
        await wait_msg.edit_text("✨ **УСПЕШНО!**\nБронь подтверждена. До встречи!")
        await state.clear()
    else:
        await wait_msg.edit_text("❌ Ошибка записи. Напишите организатору.")

# --- ВЕБ-СЕРВЕР ---
async def handle(request): return web.Response(text="Bot Alive")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
