import sqlite3
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import InputReportReasonOther, InputReportReasonViolence, InputReportReasonPornography, \
    InputReportReasonChildAbuse, InputReportReasonIllegalDrugs, InputReportReasonPersonalDetails, InputReportReasonSpam
from re import compile as compile_link
from os import listdir


TOKEN = '8071415364:AAEENYsqgexU6UP97VefHdyxdJ2Nhw5akr8'  # Замените на ваш токен бота
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# ID супер админа
SUPER_ADMIN_ID = 7030057590

# Путь к сессиям Telethon и данные
path = "n3rz4/sessions/"  # Путь к .session файлам
api_id = 17243596  # Вставьте ваш api_id
api_hash = '6365cfa9acb2a8aa4cab9642d229f6e9'  # Вставьте ваш api_hash

conn = sqlite3.connect('subscriptions.db')
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, subscription_end DATE)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY, level INTEGER)''')
conn.commit()
reasons = {
    "spam": InputReportReasonSpam(),
    "violence": InputReportReasonViolence(),
    "pornography": InputReportReasonPornography(),
    "child_abuse": InputReportReasonChildAbuse(),
    "illegal_drugs": InputReportReasonIllegalDrugs(),
    "personal_details": InputReportReasonPersonalDetails(),
    "other": InputReportReasonOther(),
}

# Стартовое сообщение
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    username = message.from_user.username
    start_date = datetime.now().strftime('%Y-%m-%d')

    # Кнопки для отправки жалоб
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("😳 Как сносить?", callback_data='how_to_demolish'),
        InlineKeyboardButton("😎 Причины для сноса", callback_data='reasons_to_demolish')
    )

    await message.answer(
        f"Здравствуйте, {username}!\n\n🤖 Бот стабильно работает. Проверка обновления от {start_date}.\n\n"
        "Воспользуйтесь кнопками для отправки жалоб.", reply_markup=keyboard)

# Обработчик нажатий на кнопки
@dp.callback_query_handler(lambda c: c.data == 'how_to_demolish' or c.data == 'reasons_to_demolish')
async def process_callback_button(callback_query: types.CallbackQuery):
    data = callback_query.data
    if data == 'how_to_demolish':
        with open('helpsnos.txt', 'r', encoding='utf-8') as file:
            text = file.read()
    elif data == 'reasons_to_demolish':
        with open('snoshelp.txt', 'r', encoding='utf-8') as file:
            text = file.read()

    await bot.send_message(callback_query.from_user.id, text)

# Проверка подписки
def check_subscription(user_id):
    cursor.execute('SELECT subscription_end FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    if result:
        subscription_end = datetime.strptime(result[0], '%Y-%m-%d')
        return subscription_end >= datetime.now()
    return False


# Проверка уровня администратора
def check_admin_level(user_id, required_level):
    cursor.execute('SELECT level FROM admins WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    if result:
        admin_level = result[0]
        return admin_level >= required_level
    return False


# Команда выдачи подписки
@dp.message_handler(commands=['addsub'])
async def add_subscription(message: types.Message):
    if check_admin_level(message.from_user.id, 1):
        args = message.text.split()
        if len(args) == 3:
            user_id = int(args[1])
            days = int(args[2])

            # Ограничение подписки для админов 1 уровня
            if check_admin_level(message.from_user.id, 1) and days > 10:
                await message.reply("Вы можете выдавать подписку максимум на 10 дней.")
                return

            subscription_end = datetime.now() + timedelta(days=days)
            cursor.execute("INSERT OR REPLACE INTO users (id, subscription_end) VALUES (?, ?)", (user_id, subscription_end.strftime('%Y-%m-%d')))
            conn.commit()
            await message.reply(f"Подписка выдана пользователю {user_id} на {days} дней.")
        else:
            await message.reply("Используйте формат команды: /addsub id количество_дней")
    else:
        await message.reply("У вас нет прав для использования этой команды.")


# Команда выдачи админских прав
@dp.message_handler(commands=['addadmin'])
async def add_admin(message: types.Message):
    if message.from_user.id == 7030057590:
        args = message.text.split()
        if len(args) == 3:
            user_id = int(args[1])
            level = int(args[2])
            if level in [1, 2]:
                cursor.execute("INSERT OR REPLACE INTO admins (id, level) VALUES (?, ?)", (user_id, level))
                conn.commit()
                await message.reply(f"Админские права уровня {level} выданы пользователю {user_id}.")
            else:
                await message.reply("Уровень администратора должен быть 1 или 2.")
        else:
            await message.reply("Используйте формат команды: /addadmin id уровень")
    else:
        await message.reply("Эта команда доступна только супер администратору.")

# Команда для отправки жалобы
@dp.message_handler(commands=['ss'])
async def ss_command(message: types.Message):
    if check_subscription(message.from_user.id):
        args = message.text.split(maxsplit=2)
        if len(args) == 3:
            reason_key = args[1].lower()
            link = args[2]

            # Проверяем наличие причины в списке
            if reason_key not in reasons:
                available_reasons = ", ".join(reasons.keys())
                await message.reply(
                    f"Причина '{reason_key}' не найдена.\nДоступные причины: {available_reasons}."
                )
                return

            # Отправляем жалобы
            reason = reasons[reason_key]
            successful_reports, failed_reports = await report_message(link, message, reason)
            await message.reply(f"Жалобы отправлены. Успешные: {successful_reports}, Ошибки: {failed_reports}")
        else:
            await message.reply(
                "Используйте формат команды: /ss причина ссылка\n\n"
                "Пример: /ss spam https://t.me/username/123"
            )
    else:
        await message.reply("У вас нет активной подписки.")

async def report_message(link: str, response_message: types.Message, reason) -> (int, int):
    successful_reports = 0
    failed_reports = 0

    # Регулярное выражение для проверки ссылки
    message_link_pattern = compile_link(r'https://t.me/(?P<username_or_chat>.+)/(?P<message_id>\d+)')
    match = message_link_pattern.search(link)

    if not match:
        await response_message.reply("Ссылка некорректна. Используйте формат: https://t.me/username/123")
        return successful_reports, failed_reports

    chat = match.group("username_or_chat")
    message_id = int(match.group("message_id"))
    sessions = [s for s in listdir(path) if s.endswith(".session")]

    # Проходим по всем доступным сессиям
    for session in sessions:
        try:
            async with TelegramClient(f"{path}{session}", api_id, api_hash) as client:
                if not await client.is_user_authorized():
                    logging.warning(f"Сессия {session} не авторизована.")
                    failed_reports += 1
                    continue

                # Проверяем, существует ли сообщение
                messages = await client.get_messages(chat, ids=message_id)
                if not messages:
                    logging.warning(f"Сообщение {message_id} не найдено в чате {chat}.")
                    failed_reports += 1
                    continue

                if messages.sender_id == 7030057590:  # Проверка на недопустимого пользователя
                    await response_message.reply(
                        "⚠️ Нельзя отправить жалобу на сообщение данного пользователя."
                    )
                    return successful_reports, failed_reports

                # Отправляем жалобу
                entity = await client.get_entity(chat)
                await client(ReportRequest(
                    peer=entity,
                    id=[message_id],
                    reason=reason,
                    message="Жалоба на сообщение. Причина: выбранная пользователем."
                ))
                successful_reports += 1

                # Логирование успешных жалоб
                logging.info(f"Успешно отправлена жалоба через сессию {session}.")

        except Exception as e:
            logging.warning(f"Ошибка в сессии {session}: {e}")
            failed_reports += 1

    # Итоговое сообщение
    await response_message.reply(
        f"✅ Завершено! Успешных жалоб: {successful_reports}, ошибок: {failed_reports}."
    )
    return successful_reports, failed_reports






async def send_report(session, chat, message_id, reason):
    """
    Отправка жалобы на сообщение с использованием указанной сессии.

    :param session: Имя файла сессии.
    :param chat: Имя пользователя или ID чата.
    :param message_id: ID сообщения для жалобы.
    :param reason: Причина жалобы.
    :return: True, если жалоба отправлена успешно, иначе False.
    """
    async with TelegramClient(f"{path}{session}", api_id, api_hash) as client:
        if not await client.is_user_authorized():
            logging.warning(f"Сессия {session} не авторизована.")
            return False

        try:
            # Проверяем существование сообщения
            messages = await client.get_messages(chat, ids=message_id)
            if not messages:
                logging.warning(f"Сообщение с ID {message_id} не найдено в чате {chat}.")
                return False

            # Отправляем жалобу
            entity = await client.get_entity(chat)
            await client(ReportRequest(
                peer=entity,
                id=[message_id],
                reason=reason,
                message="Жалоба отправлена по выбранной причине."
            ))
            logging.info(f"Жалоба на сообщение {message_id} отправлена успешно.")
            return True

        except Exception as e:
            logging.warning(f"Ошибка при отправке жалобы сессии {session}: {e}")
            return False


# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
