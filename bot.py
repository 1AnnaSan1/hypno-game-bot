import sqlite3
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
TOKEN = "7442233621:AAERkVTRXuglbgukr7VLT9QedoQWFsgj9dY"
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher()
dp["pending_appointments"] = {}

# Подключение к базе данных
conn = sqlite3.connect("appointments.db")
cursor = conn.cursor()

# Создание таблицы, если её нет
cursor.execute("""CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    phone TEXT,
                    email TEXT,
                    date TEXT,
                    time INTEGER)""")
conn.commit()

# Временное хранилище данных перед записью
dp["pending_appointments"] = {}

# Функция главного меню
def main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📅 Записаться на бесплатную сессию")]
    ])
    return keyboard

# Обработчик команды /start
@dp.message(CommandStart())
async def start_command(message: types.Message):
    text = (
        "👋 Привет! Я бот, который поможет записаться на бесплатную консультацию к психологу.\n\n"
        "Нажмите кнопку ниже, чтобы выбрать удобное время."
    )
    await message.answer(text, reply_markup=main_menu())

# Функция получения свободных часов
def get_available_times(date):
    available_hours = range(16, 22)  # Время с 16:00 до 21:00
    free_hours = []

    for hour in available_hours:
        cursor.execute("SELECT * FROM appointments WHERE date = ? AND time = ?", (date, hour))
        if not cursor.fetchone():
            free_hours.append(hour)

    return free_hours

# Функция клавиатуры с доступными часами
def generate_time_keyboard(date):
    available_times = get_available_times(date)
    if not available_times:
        return None

    keyboard = [[InlineKeyboardButton(text=f"{hour}:00", callback_data=f"time_{date}_{hour}")] for hour in available_times]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Функция клавиатуры с доступными днями
def generate_date_keyboard():
    today = datetime.today()
    keyboard = []

    for i in range(7):
        date = (today + timedelta(days=i)).strftime('%Y-%m-%d')
        if get_available_times(date):
            formatted_date = (today + timedelta(days=i)).strftime("%d.%m (%a)")
            keyboard.append([InlineKeyboardButton(text=formatted_date, callback_data=f"date_{date}")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None

# Обработчик кнопки "Записаться"
@dp.message(lambda message: message.text == "📅 Записаться на бесплатную сессию")
async def choose_date(message: types.Message):
    keyboard = generate_date_keyboard()
    if keyboard:
        await message.answer("Выберите удобный день:", reply_markup=keyboard)
    else:
        await message.answer("❌ На ближайшую неделю нет свободных мест.")

# Обработчик выбора даты
@dp.callback_query(lambda callback: callback.data.startswith("date_"))
async def choose_time(callback: types.CallbackQuery):
    selected_date = callback.data.split("_")[1]
    keyboard = generate_time_keyboard(selected_date)

    if keyboard:
        await callback.message.edit_text(f"Вы выбрали {selected_date}. Теперь выберите время:", reply_markup=keyboard)
    else:
        await callback.message.edit_text("❌ В этот день уже нет свободных мест. Выберите другую дату:",
                                         reply_markup=generate_date_keyboard())

# Функция клавиатуры для запроса номера
def phone_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📞 Отправить номер", request_contact=True)]
    ])
    return keyboard

# Обработчик выбора времени
@dp.callback_query(lambda callback: callback.data.startswith("time_"))
async def confirm_appointment(callback: types.CallbackQuery):
    _, date, hour = callback.data.split("_")
    user_id = callback.from_user.id
    hour = int(hour)

    # Сохраняем временные данные
    dp["pending_appointments"][user_id] = {"date": date, "time": hour}
    await callback.message.answer("Теперь отправьте свой номер телефона:", reply_markup=phone_keyboard())

# Обработчик номера телефона
@dp.message(lambda message: message.contact)
async def get_email(message: types.Message):
    user_id = message.from_user.id
    phone_number = message.contact.phone_number

    if user_id not in dp["pending_appointments"]:
        await message.answer("⚠️ Произошла ошибка. Попробуйте заново.")
        return

    # Сохраняем номер телефона
    dp["pending_appointments"][user_id]["phone"] = phone_number
    await message.answer("Отлично! Теперь введите ваш email:")

# Клавиатура для возврата в главное меню
def main_menu_keyboard():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🔙 Вернуться в главное меню")]
    ])

# Обработчик email и финализация записи
@dp.message(lambda message: message.text)
async def finalize_appointment(message: types.Message):
    user_id = message.from_user.id
    email = message.text

    if user_id not in dp["pending_appointments"]:
        await message.answer("⚠️ Произошла ошибка. Попробуйте заново.")
        return

    # Получаем данные
    appointment = dp["pending_appointments"].pop(user_id)
    date, time, phone = appointment["date"], appointment["time"], appointment["phone"]

    # Записываем в базу данных
    cursor.execute("INSERT INTO appointments (user_id, phone, email, date, time) VALUES (?, ?, ?, ?, ?)",
                   (user_id, phone, email, date, time))
    conn.commit()

    # Подтверждение записи + кнопка возврата
    confirmation_text = (
        f"✅ Ваша запись подтверждена!\n"
        f"📅 Дата: {date}\n"
        f"⏰ Время: {time}:00\n"
        f"📞 Телефон: {phone}\n"
        f"📧 Email: {email}\n\n"
        f"🎯 Присоединяйтесь к нашему Telegram-каналу: [ссылка]"
    )
    await message.answer(confirmation_text, reply_markup=main_menu_keyboard())

    # Уведомление психологу
    admin_id = 1936828593  # Замени на свой Telegram ID
    await bot.send_message(admin_id, f"🆕 Новая запись!\n{confirmation_text}")

# Обработчик кнопки "🔙 Вернуться в главное меню"
@dp.message(lambda message: message.text == "🔙 Вернуться в главное меню")
async def return_to_main_menu(message: types.Message):
    await message.answer("Вы в главном меню. Выберите действие:", reply_markup=main_menu())
# Функция главного меню
def main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📅 Записаться на бесплатную сессию")],
        [KeyboardButton(text="ℹ️ Узнать больше о психологе")],
        [KeyboardButton(text="📢 Перейти в ТГ канал")]
    ])
    return keyboard

# Обработчик кнопки "ℹ️ Узнать больше о психологе"
@dp.message(lambda message: message.text == "ℹ️ Узнать больше о психологе")
async def about_psychologist(message: types.Message):
    text = (
        "👩‍⚕️ О психологе:\n"
        "Меня зовут [Имя], я дипломированный психолог с [X] лет опыта работы. "
        "Помогаю людям справляться с тревогами, стрессами и находить внутреннюю гармонию. "
        "Записывайтесь на бесплатную консультацию!"
    )
    await message.answer(text)

# Обработчик кнопки "📢 Перейти в ТГ канал"
@dp.message(lambda message: message.text == "📢 Перейти в ТГ канал")
async def go_to_channel(message: types.Message):
    channel_link = "https://t.me/YOUR_CHANNEL_LINK"  # Укажи ссылку на канал
    await message.answer(f"📢 Присоединяйтесь к нашему Telegram-каналу: [Нажмите сюда]({channel_link})", parse_mode="Markdown")

# Запуск бота
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
