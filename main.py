import asyncio
import logging
import os
import sys
import re
import datetime
from collections import defaultdict

# Библиотеки Google
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN") 
ADMIN_ID = os.getenv("ADMIN_ID") 
PORT = int(os.getenv("PORT", 8080))

OFFER_LINK = "https://disk.yandex.ru/i/965-_UGNIPkaaQ"
MAX_PEOPLE_PER_SLOT = 15

# --- НАСТРОЙКИ GOOGLE ---
SHEET_NAME = "Запись на Мистерию"
GOOGLE_CREDENTIALS_FILE = "google_sheet_key.json"
DRIVE_FOLDER_ID = "1aPzxYWdh085ZjQnr2KXs3O_HMCCWpfhn" # Ваш ID папки внесен

# Хранилище занятых мест (в оперативной памяти)
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

# --- ФУНКЦИИ GOOGLE ---

async def upload_to_drive_and_save_row(data, photo_file_id):
    """Скачивает фото, загружает на Диск и делает запись в таблицу"""
    def _logic():
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
            
            # 1. Загрузка файла на Google Drive
            drive_service = build('drive', 'v3', credentials=creds)
            
            # Получаем файл из Telegram
            file_info = asyncio.run_coroutine_threadsafe(bot.get_file(photo_file_id), asyncio.get_event_loop()).result()
            file_content = asyncio.run_coroutine_threadsafe(bot.download_file(file_info.file_path), asyncio.get_event_loop()).result()
            
            file_metadata = {
                'name': f"Чек_{data['name']}_{datetime.datetime.now().strftime('%d_%m_%H%M')}.jpg",
                'parents': [DRIVE_FOLDER_ID]
            }
            media = MediaIoBaseUpload(file_content, mimetype='image/jpeg')
            drive_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
            file_link = drive_file.get('webViewLink')

            # 2. Запись в Таблицу
            client = gspread.authorize(creds)
            sheet = client.open(SHEET_NAME).sheet1
            
            row = [
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                data.get('name'),
                data.get('contact'),
                data.get('selected_date'),
                data.get('selected_time'),
                data.get('allergies'),
                file_link # Ссылка на чек
            ]
            sheet.append_row(row)
            return True
        except Exception as e:
            logging.error(f"Ошибка Google Services: {e}")
            return False

    return await asyncio.to_thread(_logic)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ КЛАВИАТУР ---

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
    await message.answer(f"{get_progress(2)}\n**Шаг 3:** Выберите **дату и место**:", reply_markup=get_dates_kb(), parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_date)

@dp.message(Registration.waiting_for_date, F.text)
async def process_date(message: types.Message, state: FSMContext):
    if message.text not in DATES_CONFIG: return
    await state.update_data(selected_date=message.text)
    await message.answer(f"{get_progress(3)}\n**Шаг 4:** Выберите **время**:", reply_markup=get_times_kb(), parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_time)

@dp.message(Registration.waiting_for_time, F.text)
async def process_time(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад к датам":
        await message.answer("Выберите дату:", reply_markup=get_dates_kb())
        await state.set_state(Registration.waiting_for_date)
        return
    
    data = await state.get_data()
    slot_id = f"{data['selected_date']}_{message.text}"
    if BOOKED_SLOTS[slot_id] >= MAX_PEOPLE_PER_SLOT:
        await message.answer("😔 На это время мест нет. Выберите другое.")
        return

    await state.update_data(selected_time=message.text)
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

@dp.callback_query(F.data == "confirm_ok")
async def confirm_ok(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✅ **ДАННЫЕ ПРИНЯТЫ**\n\nПереведите депозит **2999 руб.**\n`+79124591439` (Сбер/Т-Банк, Екатерина Б.)\n"
        "📎 **Пришлите скриншот чека сюда.**", parse_mode="Markdown"
    )
    await state.set_state(Registration.waiting_for_payment_proof)

@dp.message(Registration.waiting_for_payment_proof, F.photo)
async def process_payment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    wait_msg = await message.answer("⌛ Сохраняю данные и чек в базу...")
    
    success = await upload_to_drive_and_save_row(data, message.photo[-1].file_id)
    
    if success:
        # Увеличиваем счетчик только после успешного сохранения
        slot_id = f"{data['selected_date']}_{data['selected_time']}"
        BOOKED_SLOTS[slot_id] += 1
        
        if ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"🔥 **НОВАЯ ЗАЯВКА**\n{data['name']}\n{data['selected_date']} {data['selected_time']}")
            await message.copy_to(ADMIN_ID)
            
        await wait_msg.edit_text("✨ **УСПЕШНО!**\nБронь подтверждена. Мы свяжемся с вами скоро.")
        await state.clear()
    else:
        await wait_msg.edit_text("❌ Ошибка сохранения. Попробуйте еще раз или напишите админу.")

# --- ВЕБ-СЕРВЕР И ЗАПУСК ---
async def handle(request): return web.Response(text="Alive")

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
