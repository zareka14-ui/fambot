import asyncio
import logging
import os
import sys
import datetime
import io
import json
import base64

# Библиотеки Google
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Aiogram 3.x
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
DRIVE_FOLDER_ID = "1aPzxYWdh085ZjQnr2KXs3O_HMCCWpfhn"
SHEET_ID = "19vNVslHJEnkZCumR9e_sSc4M-YtqFWj6cLIwxojEZY0" 

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Конфигурация дат и соответствующего времени
DATES_CONFIG = {
    "📅 21 янв (ср) | 📍 Нагаево": "21 января (ср) - Нагаево",
    "📅 23 янв (пт) | 📍 Бакалинская 25": "23 января (пт) - Бакалинская 25",
    "📅 25 янв (вс) | 📍 Бакалинская 25": "25 января (вс) - Бакалинская 25"
}

# Словарь с доступным временем для каждой даты
TIMES_BY_DATE = {
    "📅 21 янв (ср) | 📍 Нагаево": ["🕙 20:00"],
    "📅 23 янв (пт) | 📍 Бакалинская 25": ["🕙 10:00", "🕖 19:00"],
    "📅 25 янв (вс) | 📍 Бакалинская 25": ["🕙 10:00", "🕖 19:00"]
}

class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_allergies = State()
    confirm_data = State()
    waiting_for_payment_proof = State()

# --- ФУНКЦИИ GOOGLE ---

async def upload_to_drive_and_save_row(data, photo_file_id):
    try:
        file_info = await bot.get_file(photo_file_id)
        file_content_io = await bot.download_file(file_info.file_path)
        content_bytes = file_content_io.read()

        def _sync_logic(content):
            encoded_key = os.getenv("GOOGLE_JSON_KEY", "").strip()
            decoded_key = base64.b64decode(encoded_key).decode('utf-8')
            key_data = json.loads(decoded_key)
            
            if "private_key" in key_data:
                key_data["private_key"] = key_data["private_key"].replace("\\n", "\n")
            
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = service_account.Credentials.from_service_account_info(key_data, scopes=SCOPES)
            
            drive_service = build('drive', 'v3', credentials=creds, cache_discovery=False)
            file_metadata = {
                'name': f"Чек_{data['name']}_{datetime.datetime.now().strftime('%d_%m')}.jpg",
                'parents': [DRIVE_FOLDER_ID]
            }
            media = MediaIoBaseUpload(io.BytesIO(content), mimetype='image/jpeg', resumable=True)
            drive_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
            
            client = gspread.authorize(creds)
            sheet = client.open_by_key(SHEET_ID).sheet1
            
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
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=d)] for d in DATES_CONFIG.keys()], resize_keyboard=True)

def get_times_kb(times_list):
    buttons = [[KeyboardButton(text=t)] for t in times_list]
    buttons.append([KeyboardButton(text="⬅️ Назад к датам")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- ХЭНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "✨ **МИСТЕРИЯ «СТАЛЬ • СОЛЬ • ОГОНЬ • ШАМАН и МАГИЯ РОДА»**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Добро пожаловать в сакральное пространство. Для нашей встречи я подготовлю индивидуальный набор артефактов для каждого участника, для этого нам нужно познакомиться.\n\n"
        "Нажмите кнопку ниже, чтобы начать регистрацию"
    )
    await message.answer(welcome_text, reply_markup=get_start_kb(), parse_mode="Markdown")

@dp.message(F.text == "🚀 Начать регистрацию")
async def start_form(message: types.Message, state: FSMContext):
    await message.answer("Шаг 1: Введите ваше **ФИО**:", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Шаг 2: Ваш **номер телефона** или @username для связи и добавления в закрытый чат мероприятия:")
    await state.set_state(Registration.waiting_for_contact)

@dp.message(Registration.waiting_for_contact, F.text)
async def process_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await message.answer("Шаг 3: Выберите **дату** нашей встречи:", reply_markup=get_dates_kb())
    await state.set_state(Registration.waiting_for_date)

@dp.message(Registration.waiting_for_date, F.text)
async def process_date(message: types.Message, state: FSMContext):
    if message.text not in DATES_CONFIG:
        return
    
    await state.update_data(selected_date=message.text)
    
    # Динамически получаем список времени для выбранной даты
    available_times = TIMES_BY_DATE.get(message.text, [])
    
    await message.answer(
        "Шаг 4: Выберите удобное **время**:", 
        reply_markup=get_times_kb(available_times),
        parse_mode="Markdown"
    )
    await state.set_state(Registration.waiting_for_time)

@dp.message(Registration.waiting_for_time, F.text)
async def process_time(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад к датам":
        await message.answer("Шаг 3: Выберите **дату**:", reply_markup=get_dates_kb())
        await state.set_state(Registration.waiting_for_date)
        return
    
    user_data = await state.get_data()
    selected_date = user_data.get('selected_date')
    valid_times = TIMES_BY_DATE.get(selected_date, [])

    if message.text not in valid_times:
        return

    await state.update_data(selected_time=message.text)
    await message.answer("Шаг 5: Есть ли у вас **аллергия** на травы или эфирные масла? (Если нет — напишите «Нет»)", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Registration.waiting_for_allergies)

@dp.message(Registration.waiting_for_allergies, F.text)
async def process_allergies(message: types.Message, state: FSMContext):
    await state.update_data(allergies=message.text)
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Прочитать оферту", url=OFFER_LINK)],
        [InlineKeyboardButton(text="✅ Все верно", callback_data="confirm_ok")]
    ])
    summary = (
        f"**ПРОВЕРЬТЕ ВАШИ ДАННЫЕ:**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 **ФИО:** {data['name']}\n"
        f"📞 **Связь:** {data['contact']}\n"
        f"🗓 **Запись:** {data['selected_date']} в {data['selected_time']}\n"
        f"⚠️ **Аллергии:** {data['allergies']}"
    )
    await message.answer(summary, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(Registration.confirm_data)

@dp.callback_query(F.data == "confirm_ok")
async def process_confirm(callback: types.CallbackQuery, state: FSMContext):
    payment_text = (
        "✅ **ПОЧТИ ГОТОВО**\n"
        "Для завершения бронирования необходимо оплатить участие (**2999 р.**) и прислать скриншот чека.\n\n"
        "📍 **Реквизиты:** `+79124591439` (Сбер/Т-Банк)\n Назначение платежа укажите "Благотворительный взнос""
        "👤 Екатерина Б."
    )
    await callback.message.edit_text(payment_text, parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_payment_proof)

@dp.message(Registration.waiting_for_payment_proof, F.photo)
async def process_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # 1. Уведомление админу
    if ADMIN_ID:
        try:
            report = (
                f"**НОВАЯ ЗАЯВКА НА МИСТЕРИЮ**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 **ФИО:** {data.get('name')}\n"
                f"📞 **Связь:** {data.get('contact')}\n"
                f"🗓 **Дата/Время:** {data.get('selected_date')} {data.get('selected_time')}\n"
                f"⚠️ **Аллергии:** {data.get('allergies')}\n"
                f"🆔 ID: `{message.from_user.id}`\n"
            )
            await bot.send_message(ADMIN_ID, report, parse_mode="Markdown")
            await message.copy_to(ADMIN_ID)
        except Exception as e:
            logging.error(f"Ошибка уведомления админа: {e}")

    # 2. Обработка Google
    wait_msg = await message.answer("⌛ Сохраняю ваше место в сакральном списке...")
    success = await upload_to_drive_and_save_row(data, message.photo[-1].file_id)
    
    # 3. Финальный ответ
    final_text = "✨ **БЛАГОДАРИМ!**\nВаша бронь подтверждена. Я подготовлю всё необходимое к нашей встрече. Не забудьте взять с собой удобную одежду, теплые носки и плед. 
По желанию что-то к чаю.До встречи на Мистерии ✨"
    await wait_msg.edit_text(final_text)
    await state.clear()

# --- WEB SERVER ---
async def handle(request): return web.Response(text="OK")

async def main():
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
