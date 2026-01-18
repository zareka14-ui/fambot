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
DRIVE_FOLDER_ID = "1aPzxYWdh085ZjQnr2KXs3O_HMCCWpfhn"
SHEET_NAME = "Запись на Мистерию"

# Временное хранилище (сбрасывается при перезагрузке Render)
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

DATES_CONFIG = {
    "📅 21 янв (ср) | 📍 Иглино": "21 января (ср) - Иглино",
    "📅 23 янв (пт) | 📍 Бакалинская 25": "23 января (пт) - Бакалинская 25",
    "📅 25 янв (вс) | 📍 Бакалинская 25": "25 января (вс) - Бакалинская 25"
}
TIMES_CONFIG = ["🕙 10:00", "🕖 19:00"]

# --- ФУНКЦИИ GOOGLE ---

async def upload_to_drive_and_save_row(data, photo_file_id):
    try:
        file_info = await bot.get_file(photo_file_id)
        file_content_io = await bot.download_file(file_info.file_path)
        content_bytes = file_content_io.read()

        def _sync_logic(content):
            env_key = os.getenv("GOOGLE_JSON_KEY", "").strip()
            if not env_key:
                raise ValueError("GOOGLE_JSON_KEY is empty")
            
            key_data = json.loads(env_key)
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            
            # ИСПРАВЛЕННЫЙ МЕТОД НИЖЕ
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_data, scope)
            
            # Drive API
            drive_service = build('drive', 'v3', credentials=creds, cache_discovery=False)
            file_metadata = {
                'name': f"Чек_{data['name']}_{datetime.datetime.now().strftime('%d_%m_%H%M')}.jpg",
                'parents': [DRIVE_FOLDER_ID]
            }
            media = MediaIoBaseUpload(io.BytesIO(content), mimetype='image/jpeg', resumable=True)
            drive_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
            
            # Sheets API
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
        logging.error(f"Критическая ошибка Google Services: {e}")
        return False

# --- КЛАВИАТУРЫ ---

def get_start_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚀 Начать регистрацию")]], resize_keyboard=True)

def get_dates_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=d)] for d in DATES_CONFIG.keys()], resize_keyboard=True)

def get_times_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t)] for t in TIMES_CONFIG] + [[KeyboardButton(text="⬅️ Назад к датам")]], resize_keyboard=True)

# --- ХЭНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("✨ **МИСТЕРИЯ**\nНачнем регистрацию?", reply_markup=get_start_kb(), parse_mode="Markdown")

@dp.message(F.text == "🚀 Начать регистрацию")
async def start_form(message: types.Message, state: FSMContext):
    await message.answer("Шаг 1: Введите ваше **ФИО**:", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Шаг 2: Ваш **номер телефона** или @username:")
    await state.set_state(Registration.waiting_for_contact)

@dp.message(Registration.waiting_for_contact, F.text)
async def process_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await message.answer("Шаг 3: Выберите **дату**:", reply_markup=get_dates_kb())
    await state.set_state(Registration.waiting_for_date)

@dp.message(Registration.waiting_for_date, F.text)
async def process_date(message: types.Message, state: FSMContext):
    if message.text not in DATES_CONFIG: return
    await state.update_data(selected_date=message.text)
    await message.answer("Шаг 4: Выберите **время**:", reply_markup=get_times_kb())
    await state.set_state(Registration.waiting_for_time)

@dp.message(Registration.waiting_for_time, F.text)
async def process_time(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад к датам":
        await message.answer("Шаг 3: Выберите **дату**:", reply_markup=get_dates_kb())
        await state.set_state(Registration.waiting_for_date)
        return
    await state.update_data(selected_time=message.text)
    await message.answer("Шаг 5: Есть ли **аллергия**? (Если нет — напишите «Нет»)")
    await state.set_state(Registration.waiting_for_allergies)

@dp.message(Registration.waiting_for_allergies, F.text)
async def process_allergies(message: types.Message, state: FSMContext):
    await state.update_data(allergies=message.text)
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Оферта", url=OFFER_LINK)],
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_ok")]
    ])
    await message.answer(f"**ПРОВЕРЬТЕ ДАННЫЕ:**\n👤 {data['name']}\n📞 {data['contact']}\n🗓 {data['selected_date']} {data['selected_time']}", reply_markup=kb, parse_mode="Markdown")
    await state.set_state(Registration.confirm_data)

@dp.callback_query(F.data == "confirm_ok")
async def process_confirm(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✅ Пришлите скриншот чека (**2999 р.**)\nРеквизиты: `+79124591439` Екатерина Б.")
    await state.set_state(Registration.waiting_for_payment_proof)

@dp.message(Registration.waiting_for_payment_proof, F.photo)
async def process_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # Сначала Вам в личку
    if ADMIN_ID:
        try:
            report = f"🔥 **НОВАЯ ОПЛАТА**\n👤 {data.get('name')}\n📞 {data.get('contact')}\n🗓 {data.get('selected_date')} {data.get('selected_time')}"
            await bot.send_message(ADMIN_ID, report)
            await message.copy_to(ADMIN_ID)
        except Exception as e:
            logging.error(f"Admin notify error: {e}")

    wait_msg = await message.answer("⌛ Секунду, завершаю регистрацию...")
    
    # Пытаемся в Google
    success = await upload_to_drive_and_save_row(data, message.photo[-1].file_id)
    
    await wait_msg.edit_text("✨ **БЛАГОДАРИМ!**\nВаша бронь подтверждена. До встречи!")
    await state.clear()

# --- SERVER ---
async def handle(request): return web.Response(text="OK")

async def main():
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
