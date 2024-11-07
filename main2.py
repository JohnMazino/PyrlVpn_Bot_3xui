import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, PreCheckoutQuery, LabeledPrice, Message  
from aiogram.utils.keyboard import InlineKeyboardBuilder 
from aiogram.filters.command import Command
from yoomoney import Quickpay
from yoomoney import Client as YClient
from datetime import datetime, timedelta
from py3xui import Api, Client
import os

os.environ["XUI_HOST"] = "https://mazino.freemyip.com:25679/9ILhEoYEonXBKAd"
os.environ["XUI_USERNAME"] = "TzRKWlLfiX"
os.environ["XUI_PASSWORD"] = "zM1yFiDAjt"
  
# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Объект бота
bot = Bot(token="7734786127:AAE3X--UfFc0_-2H-M2RBl9hImXndRNy0A4")
# токен юмани
token = "4100118871649407.284EA3B8F94AEA1802F41597F3E43D5096F5511BC05C51FDAC56CE4BACBADBEC096737AA7AF7CE3ECAD725D8B00A681F7E74E5F18003A1B7CEFE77CAE4F3DDC2804074708819A47B3ECA1C1B66DD0099194631CB438E6A3566BF17980634F7770449988E87442D2B89CE30D6CF602CB825635E7E52F4AC2463CA7156E0BE2277"

ADMIN_ID = 1044887762

# Диспетчер
dp = Dispatcher()

#проверка подписки 
async def is_user_subscribed(user_id: int, channel_username: str) -> bool:
    try:
        chat_member = await bot.get_chat_member(channel_username, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Failed to check subscription: {e}")
        return False

# Подключение к SQLite
DATABASE = 'users.db'
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT UNIQUE NOT NULL,
                subscription_date TIMESTAMP,
                subscription_type TEXT NOT NULL
            )
        ''')
        conn.commit()

# Функция для добавления пользователя в базу данных
def add_user(user_id: int, subscription_type: str = '7_days'):
    subscription_date = datetime.now()
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id, subscription_date, subscription_type) VALUES (?, ?, ?)",
                       (user_id, subscription_date.strftime('%Y-%m-%d %H:%M:%S'), subscription_type))
        conn.commit()

# Функция для обновления даты подписки и типа подписки
def update_subscription_date(user_id: int, subscription_date: str, subscription_type: str):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET subscription_date = ?, subscription_type = ? WHERE user_id = ?",
                       (subscription_date, subscription_type, user_id))
        conn.commit()

# Функция для получения даты окончания подписки
def get_subscription_expiry(user_id: int):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT subscription_date, subscription_type FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result and result[0]:
            subscription_date = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
            subscription_type = result[1]
            # Условие для определения срока действия
            if subscription_type == '7_days':
                expiry_date = subscription_date + timedelta(days=7)
            elif subscription_type == '30_days':
                expiry_date = subscription_date + timedelta(days=30)
            else:
                return None  # Если тип подписки не определен, возвращаем None
            return expiry_date
        return None

#Эта функция извлекает всех пользователей из базы данных
def get_all_users():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        return cursor.fetchall()

#Эта функция извлекает конкретного пользователя по его user_id
def get_user(user_id: int):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()  # Возвращает None, если пользователь не найден

class MyForm(StatesGroup):
    message = State()

#команда для админа(оповещение и реклама) 
@dp.message(Command(commands=["send_all"]))
async def admin_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if str(user_id) == str(ADMIN_ID):
        await message.answer('Напишите сообщение для рассылки')
        await state.set_state(MyForm.message)

@dp.message(MyForm.message)
async def handle_message_for_broadcast(message: types.Message, state: FSMContext):
    state_message = message.text
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        users = get_all_users()
        for user in users:
            await bot.send_message(user[0], state_message)

        await state.clear()  # Очищаем состояние после рассылки        

#функция для 7 дней бесплатно
async def perform_action_for_new_user(user_id: int):
    api = Api("https://mazino.freemyip.com:25679/9ILhEoYEonXBKAd", "TzRKWlLfiX", "zM1yFiDAjt")
    api = Api.from_env()
    api.login()
    client = api.client.get_by_email(user_id)
    # Создание пользователя
    epoch = datetime.fromtimestamp(0)
    x_time = int((datetime.now() - epoch).total_seconds() * 1000.0)
    x_time += 86400000 * 7 - 10800000  # 7 дней в миллисекундах
    
    new_client = Client(
        id=str(user_id),
        email=str(user_id),
        flow=str("xtls-rprx-vision"),
        enable=True,
        expiryTime=str(x_time)
    )
    
    inbound_id = 1
    api.client.add(inbound_id, [new_client])  # Добавляем нового клиента

    # Обновляем дату подписки в базе данных на 7 дней
    update_subscription_date(user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), subscription_type='7_days')

    
    # Отправляем сообщение с информацией о подписке
    await bot.send_message(
        user_id,
        "Я вижу вы новый пользователь\n(⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)\n\n"
        "Ваш VPN доступ на 7 дней\n" 
        f"```VPN vless://{user_id}@mazino.freemyip.com:443?type=tcp&security=reality&pbk=KlSWg1lI5LM--SBHsodp2xO2T-UFKKhsL6xFnYD6P3o&fp=firefox&sni=yahoo.com&sid=5dacee7cbc26f2&spx=%2F&flow=xtls-rprx-vision#VPN-{user_id}```",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

#кнопка для звезд 
def payment_keyboard():  
    builder = InlineKeyboardBuilder()  
    builder.button(text=f"Оплатить 50 ⭐️", pay=True)  
    return builder.as_markup()

#создание платежа звездами
async def send_invoice_handler(message: Message):  
    prices = [LabeledPrice(label="XTR", amount=50)]  
    await message.answer_invoice(  
        title="Подписка PYRL VPN",  
        description="Купить подписку",  
        prices=prices,  
        provider_token="",  
        payload="channel_support",  
        currency="XTR",  
        reply_markup=payment_keyboard(),  
    )

# проверка платежа звездами
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):  
    await pre_checkout_query.answer(ok=True)

# благодарность за покупку 
async def success_payment_handler(message: Message):
    user_id = message.from_user.id
    #создание пользователя
    api = Api("https://mazino.freemyip.com:25679/9ILhEoYEonXBKAd", "TzRKWlLfiX", "zM1yFiDAjt")
    api = Api.from_env()
    api.login()
    epoch = datetime.fromtimestamp(0)
    x_time = int((datetime.now() - epoch).total_seconds() * 1000.0)
    x_time += 86400000 * 30 - 10800000
    
    new_client = Client(
                id=str(user_id), 
                email=str(user_id), 
                flow=str("xtls-rprx-vision"), 
                enable=True, 
                expiryTime=str(x_time))
    inbound_id = 1
    api.client.add(inbound_id, [new_client])
    update_subscription_date(user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), subscription_type='30_days')
    await message.answer(text="🥳Спасибо за вашу поддержку!(♡°▽°♡)\n"
                                f"```VPN vless://{user_id}@mazino.freemyip.com:443?type=tcp&security=reality&pbk=KlSWg1lI5LM--SBHsodp2xO2T-UFKKhsL6xFnYD6P3o&fp=firefox&sni=yahoo.com&sid=5dacee7cbc26f2&spx=%2F&flow=xtls-rprx-vision#VPN-{user_id}```",
                                parse_mode='Markdown',
                                disable_web_page_preview=True)

#обработчики для звезд 
dp.message.register(send_invoice_handler, Command(commands="donate"))
dp.pre_checkout_query.register(pre_checkout_handler)
dp.message.register(success_payment_handler, F.successful_payment)
  
# Создаем объекты инлайн-кнопок
MAC = InlineKeyboardButton(text='MAC', callback_data='MAC_pressed')
IOS = InlineKeyboardButton(text='IOS', callback_data='IOS_pressed')
WINDOWS = InlineKeyboardButton(text='WINDOWS', callback_data='WINDOWS_pressed')
ANDROID = InlineKeyboardButton(text='ANDROID', callback_data='ANDROID_pressed')
BACK_TO_MENU = InlineKeyboardButton(text='Назад к инструкциям', callback_data='back_to_menu')
INFO_BUTTON = InlineKeyboardButton(text='Информация', callback_data='info_pressed')
SUBSCRIBE_BUTTON = InlineKeyboardButton(text='Подписка', callback_data='subscribe_pressed')
INSTRUCTIONS_BUTTON = InlineKeyboardButton(text='Инструкции', callback_data='instructions_pressed')
MENU_BUTTON = InlineKeyboardButton(text='Меню', callback_data='menu_pressed')
CHECK_PAYMENT_BUTTON = InlineKeyboardButton(text='Проверить оплату/подписку', callback_data='check_payment')

# Создаем объект инлайн-клавиатуры с двумя столбцами
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [MAC, IOS],
    [WINDOWS, ANDROID],
    [MENU_BUTTON]
])

# Клавиатура для меню
menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [INFO_BUTTON, SUBSCRIBE_BUTTON, INSTRUCTIONS_BUTTON]
])

@dp.callback_query(F.data == 'check_payment')
async def check_payment(callback: CallbackQuery):

    # получаем id пользователя
    user_id = callback.from_user.id

    # на всякий случай добавлаем его, ну вдруг
    add_user(user_id)
    client = YClient(token)
    
    # Получаем историю операций
    history = client.operation_history()

    # Используем ID пользователя как label для проверки
    user_label = str(user_id)

    found = False # флаг проверки

    for operation in history.operations:
        if operation.label == user_label: #and operation.amount == 105.0:  # Проверяем, совпадает ли label и сумма с искомым
            found = True
            
            # Получаем дату операции и сравниваем с текущим временем
            operation_time = operation.datetime  
            #operation_date = datetime.fromtimestamp(operation_time)  # Преобразуем строку в datetime
            current_date = datetime.now()


             # Проверяем, прошло ли 30 дней с момента операции
            if (current_date - operation_time) < timedelta(days=30):            
                
                api = Api("https://mazino.freemyip.com:25679/9ILhEoYEonXBKAd", "TzRKWlLfiX", "zM1yFiDAjt")
                api = Api.from_env()
                api.login()
                client = api.client.get_by_email(user_id)                
                
                if client is None:
                
                    #создание пользователя
                    epoch = datetime.fromtimestamp(0)
                    x_time = int((datetime.now() - epoch).total_seconds() * 1000.0)
                    x_time += 86400000 * 30 - 10800000
                    
                    new_client = Client(
                    id=str(user_id), 
                    email=str(user_id), 
                    flow=str("xtls-rprx-vision"), 
                    enable=True, 
                    expiryTime=str(x_time))
                    inbound_id = 1
                    api.client.add(inbound_id, [new_client])
                    # Обновляем дату подписки в базе данных
                    
                    update_subscription_date(user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), subscription_type='30_days')
            
                    await callback.message.answer(
                        "Спасибо за оформление подписки\n(⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)\n\n"
                        f"``` vless://{user_id}@mazino.freemyip.com:443?type=tcp&security=reality&pbk=KlSWg1lI5LM--SBHsodp2xO2T-UFKKhsL6xFnYD6P3o&fp=firefox&sni=yahoo.com&sid=5dacee7cbc26f2&spx=%2F&flow=xtls-rprx-vision#VPN-{user_id}```",
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                else:
                    await callback.message.answer(
                        "Ваша подписка еще активна"
                    )
                break
            else:
                await callback.message.answer("Ваша подписка истекла. Пожалуйста, оплатите снова.")
            break
    if not found:
        await callback.message.answer(f"Бот не нашел оплаты по id {user_label} , проверьте прошла ли оплата или обратитесь в поддержку.")

# Здесь инструкция для MAC
@dp.callback_query(F.data == 'MAC_pressed')
async def process_mac_button(callback: CallbackQuery):
    user_id = callback.from_user.id  # Получаем ID пользователя
    # Проверка подписки
    channel_username = "@PYRLVPN" 
    subscribed = await is_user_subscribed(user_id, channel_username)

    if not subscribed:
        await callback.message.edit_text(
            text="🚫 Вы должны подписаться на наш канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return
    await callback.message.edit_text(
        text='К сожалению инструкция для MAC будет позже (⌣̀_⌣́)',  
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[BACK_TO_MENU]])
    )

# Здесь инструкция для IOS
@dp.callback_query(F.data == 'IOS_pressed')
async def process_ios_button(callback: CallbackQuery):
    user_id = callback.from_user.id  # Получаем ID пользователя
    # Проверка подписки
    channel_username = "@PYRLVPN" 
    subscribed = await is_user_subscribed(user_id, channel_username)

    if not subscribed:
        await callback.message.edit_text(
            text="🚫 Вы должны подписаться на наш канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return
    await callback.message.edit_text(
        text='К сожалению инструкция для IOS будет позже (⌣̀_⌣́)',  
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[BACK_TO_MENU]])
    )

# Здесь инструкция для WINDOWS
@dp.callback_query(F.data == 'WINDOWS_pressed')
async def process_windows_button(callback: CallbackQuery):
    user_id = callback.from_user.id  # Получаем ID пользователя
    # Проверка подписки
    channel_username = "@PYRLVPN" 
    subscribed = await is_user_subscribed(user_id, channel_username)

    if not subscribed:
        await callback.message.edit_text(
            text="🚫 Вы должны подписаться на наш канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return
    await callback.message.edit_text(
        text='1. Скачайте приложение [Nekoray](https://github.com/MatsuriDayo/nekoray/releases/download/3.26/nekoray-3.26-2023-12-09-windows64.zip) из Github \n\n'
            "2. Разархивируйте в удобное место и запустите nekoray.exe, при запуске выберите Sing-box\n\n"
            "3. Скопируйте ссылку на подключение в буфер обмена\n\n"
            "4. В приложении нажмите сервер -> добавить из буфер обмена\n\n"
            "5. Запустите режим TUN в верхнем правом углу, нажмите правой кнопкой по своему профилю -> Запустить\n\n"
            "P.S. для юзеров [линукс](https://github.com/MatsuriDayo/nekoray/releases) (^人^)",
        parse_mode='Markdown', 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[BACK_TO_MENU]])
    )

# Здесь инструкция для ANDROID
@dp.callback_query(F.data == 'ANDROID_pressed')
async def process_android_button(callback: CallbackQuery):
    user_id = callback.from_user.id  # Получаем ID пользователя
    # Проверка подписки
    channel_username = "@PYRLVPN" 
    subscribed = await is_user_subscribed(user_id, channel_username)

    if not subscribed:
        await callback.message.edit_text(
            text="🚫 Вы должны подписаться на наш канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return
    await callback.message.edit_text(
        text='1. Скачате приложение [Nekobox](https://github.com/Matsuridayo/NekoBoxForAndroid/releases) обязательно с github\n(это важно(￣ヘ￣))\n\n'
        "2. Скопируйте ссылку на подключение в буфер обмена\n\n"
        "3. Нажмите на файлик с плючиком в верхнем правом углу -> из буфер обмена\n\n"
        "4. Активируйте кнопкой ввиде телеграммы снизу по центру\n\n",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[BACK_TO_MENU]])
    )

@dp.callback_query(F.data == 'back_to_menu')
async def back_to_menu(callback: CallbackQuery):
    user_id = callback.from_user.id  # Получаем ID пользователя
    # Проверка подписки
    channel_username = "@PYRLVPN" 
    subscribed = await is_user_subscribed(user_id, channel_username)

    if not subscribed:
        await callback.message.edit_text(
            text="🚫 Вы должны подписаться на наш канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return
    await callback.message.edit_text(
        text='🎉 Добро пожаловать в PYRL VPN! 👾\n\n'
         'Ваш безопасный и надежный спутник в мире интернета! Подключение займёт всего пару мгновений (─‿‿─).\n\n'
         'Не забудьте подписаться на наш канал [здесь](https://t.me/PYRLVPN), чтобы быть в курсе всех новостей и акций!\n\n'
         'Чтобы начать, просто выберите своё устройство, и я пришлю инструкцию по активации!\n\n'
         "Ожидайте удивительных возможностей! ^-^ ",
        reply_markup=keyboard,
        parse_mode='Markdown',
    )

@dp.callback_query(F.data == 'menu_pressed')
async def menu_pressed(callback: CallbackQuery):
    user_id = callback.from_user.id  # Получаем ID пользователя
    # Проверка подписки
    channel_username = "@PYRLVPN" 
    subscribed = await is_user_subscribed(user_id, channel_username)

    if not subscribed:
        await callback.message.edit_text(
            text="🚫 Вы должны подписаться на наш канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return

    # Получаем дату окончания подписки
    expiry_date = get_subscription_expiry(user_id)

    if expiry_date:
        remaining_time = expiry_date - datetime.now()
        remaining_days = remaining_time.days
        remaining_hours, remainder = divmod(remaining_time.seconds, 3600)
        remaining_minutes, remaining_seconds = divmod(remainder, 60)

        response_text = (
            f'Ваш ID: {user_id}\n'
            f'Осталось времени до окончания подписки: {remaining_days} дней, '
            f'{remaining_hours} часов, {remaining_minutes} минут\n'
            'Контакты техподдержки: [поддержка](https://t.me/gamplez)\n\n'
        )
    else:
        response_text = (
            'У вас нет активной подписки.\n'
            f'Ваш ID: {user_id}\n'
            'Контакты техподдержки: [поддержка](https://t.me/gamplez)\n\n'
        )
    await callback.message.edit_text(response_text, reply_markup=menu_keyboard, parse_mode='Markdown')

@dp.callback_query(F.data == 'instructions_pressed')
async def instructions_pressed(callback: CallbackQuery):
    user_id = callback.from_user.id  # Получаем ID пользователя
    # Проверка подписки
    channel_username = "@PYRLVPN" 
    subscribed = await is_user_subscribed(user_id, channel_username)

    if not subscribed:
        await callback.message.edit_text(
            text="🚫 Вы должны подписаться на наш канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return
    await callback.message.edit_text(
        text='🎉 Добро пожаловать в PYRL VPN! 👾\n\n'
         'Ваш безопасный и надежный спутник в мире интернета! Подключение займёт всего пару мгновений (─‿‿─).\n\n'
         'Не забудьте подписаться на наш канал [здесь](https://t.me/PYRLVPN), чтобы быть в курсе всех новостей и акций!\n\n'
         'Чтобы начать, просто выберите своё устройство, и я пришлю инструкцию по активации!\n\n'
         "Ожидайте удивительных возможностей! ^-^ ",
        reply_markup=keyboard,
        parse_mode='Markdown',
    )

@dp.callback_query(F.data == 'info_pressed')
async def info_pressed(callback: CallbackQuery):
    user_id = callback.from_user.id  # Получаем ID пользователя
    # Проверка подписки
    channel_username = "@PYRLVPN" 
    subscribed = await is_user_subscribed(user_id, channel_username)

    if not subscribed:
        await callback.message.edit_text(
            text="🚫 Вы должны подписаться на наш канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return
    info_text = (
        "[Автор](https://github.com/JohnMazino) проекта\n\n"
        "Пока что доступен только регион Нидерланды (︶︹︺)\n\n"
        "Vpn основан на протоколе vless и технологии xtls-rprx-vision для обхода блокировок и скрытия трафика под сайт www.yahoo.com \n\n"
        "Бот привязан к консоле 3x-ui, что дает возможность создать для каждого юзера отдельное подключение и профиль\n\n"
        "При покупке подписке вы получаете доступ на 30 дней, безлимит по трафику и подключенным устройствам, а так же возможность качать любой контент на BitTorrent(ну и в других клиентах тоже)(＾▽＾)\n\n"
        "Если возникли вопросы, проблемы с работой бота или вы хотите купить код бота, обращайтесь в [поддержку](https://t.me/gamplez)"
    )
    await callback.message.edit_text(info_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(inline_keyboard=[[MENU_BUTTON]]))

@dp.callback_query(F.data =='subscribe_pressed')
async def subscribe_pressed(callback: CallbackQuery):
    # создание платежа
    user_id = callback.from_user.id
    quickpay = Quickpay(
            receiver="4100118871649407",
            quickpay_form="shop",
            targets="subscribe pyrl vpn",
            paymentType="SB",
            sum=105,
            label=str(user_id)
            )
    pay_button = InlineKeyboardButton(text='Оплатить картой/юмани', url=quickpay.redirected_url)
    star_payment_button = InlineKeyboardButton(text='Оплатить 50 ⭐️', callback_data='donate_star')

    subscribe_text = (
        "Информация о подписке: после оплаты и проверки вам выдается личная ссылка на использование(регион Нидерландах), инструкцию по использовании можно посмотреть командой /start или через главное меню бота\n\n"
        "Также есть функция оплаты звездами по команде /donate\n\n"
        "Вы оформляете подписку на 30 дней, которая начнется сразу после оплаты   (• ω •) \n\n "
        "ВНИМАНИЕ❗❗❗ В боте нет функции продления подписки. Повторную оплату производить только в случае, если бот напишет 'Продлить подписку' при нажатии кнопки 'Проверить'."
        )
    await callback.message.edit_text(subscribe_text,  parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(inline_keyboard=[[pay_button, star_payment_button], [CHECK_PAYMENT_BUTTON], [MENU_BUTTON]]))

# /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    channel_username = "@PYRLVPN"
    subscribed = await is_user_subscribed(user_id, channel_username)
    

    if not subscribed:
        await message.answer(
            text="🚫 Вы должны подписаться на наш канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return

    # Проверяем, существует ли пользователь в базе данных
    existing_user = get_user(user_id)  # Функция для получения пользователя из базы данных

    if existing_user is None:
        # Если пользователь новый, добавляем его и выполняем нужные действия
        add_user(user_id, subscription_type='7_days')

        # Выполняем какое-то действие для нового пользователя
        await perform_action_for_new_user(user_id)

    await message.answer(
        text='🎉 Добро пожаловать в PYRL VPN! 👾\n\n'
             'Ваш безопасный и надежный спутник в мире интернета! Подключение займёт всего пару мгновений (─‿‿─).\n\n'
             'Не забудьте подписаться на наш канал [здесь](https://t.me/PYRLVPN), чтобы быть в курсе всех новостей и акций!\n\n'
             'Чтобы начать, просто выберите своё устройство, и я пришлю инструкцию по активации!\n\n'
             "Ожидайте удивительных возможностей! ^-^ ",
        parse_mode='Markdown',
        disable_web_page_preview=False,
        reply_markup=keyboard
    )

# /menu
@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    user_id = message.from_user.id  # Получаем ID пользователя
    # Проверка подписки
    channel_username = "@PYRLVPN" 
    subscribed = await is_user_subscribed(user_id, channel_username)

    if not subscribed:
        await message.answer(
            text="🚫 Вы должны подписаться на наш канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return

    # Получаем дату окончания подписки
    expiry_date = get_subscription_expiry(user_id)

    if expiry_date:
        remaining_time = expiry_date - datetime.now()
        remaining_days = remaining_time.days
        remaining_hours, remainder = divmod(remaining_time.seconds, 3600)
        remaining_minutes, remaining_seconds = divmod(remainder, 60)

        response_text = (
            f'Ваш ID: {user_id}\n'
            f'Осталось времени до окончания подписки: {remaining_days} дней, '
            f'{remaining_hours} часов, {remaining_minutes} минут\n'
            'Контакты техподдержки: [поддержка](https://t.me/gamplez)\n\n'
        )
    else:
        response_text = (
            'У вас нет активной подписки.\n'
            f'Ваш ID: {user_id}\n'
            'Контакты техподдержки: [поддержка](https://t.me/gamplez)\n\n'
        )

    await message.answer(response_text, reply_markup=menu_keyboard, parse_mode='Markdown')

# /info
@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    user_id = message.from_user.id
    channel_username = "@PYRLVPN"  # Replace with your channel username
    subscribed = await is_user_subscribed(user_id, channel_username)

    if not subscribed:
        await message.answer(
            text="🚫 Вы должны подписаться на канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return
    info_text = (
        "[Автор](https://github.com/JohnMazino) проекта\n\n"
        "Пока что доступен только регион Нидерланды (︶︹︺)\n\n"
        "Vpn основан на протоколе vless и технологии xtls-rprx-vision для обхода блокировок и скрытия трафика под сайт www.yahoo.com \n\n"
        "Бот привязан к консоле 3x-ui, что дает возможность создать для каждого юзера отдельное подключение и профиль\n\n"
        "При покупке подписке вы получаете доступ на 30 дней, безлимит по трафику и подключенным устройствам, а так же возможность качать любой контент на BitTorrent(ну и в других клиентах тоже)(＾▽＾)\n\n"
        "Если возникли вопросы, проблемы с работой бота или вы хотите купить код бота, обращайтесь в [поддержку](https://t.me/gamplez)"
    )
    await message.answer(info_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[MENU_BUTTON]]), parse_mode='Markdown')

# /subscribe
@dp.message(Command("subscribe"))
async def subscribe(message: types.Message):
# создание платежа
    user_id = message.from_user.id
    channel_username = "@PYRLVPN"  # Replace with your channel username
    subscribed = await is_user_subscribed(user_id, channel_username)

    if not subscribed:
        await message.answer(
            text="🚫 Вы должны подписаться на наш канал, чтобы использовать этого бота.\n"
                 f"Пожалуйста, перейдите по ссылке: {channel_username}",
            parse_mode='Markdown'
        )
        return
    quickpay = Quickpay(
            receiver="4100118871649407",
            quickpay_form="shop",
            targets="subscribe pyrl vpn",
            paymentType="SB",
            sum=105,
            label=str(user_id)
            )
    pay_button = InlineKeyboardButton(text='Оплатить картой/юмани', url=quickpay.redirected_url)
    star_payment_button = InlineKeyboardButton(text='Оплатить 50 ⭐️', callback_data='donate_star')
    
    
    
    subscribe_text = (
        "Информация о подписке: после оплаты и проверки вам выдается личная ссылка на использование(регион Нидерландах), инструкцию по использовании можно посмотреть командой /start или через главное меню бота\n\n"
        "Также есть функция оплаты звездами по команде /donate\n\n"
        "Вы оформляете подписку на 30 дней, которая начнется сразу после оплаты   (• ω •) \n\n "
        "ВНИМАНИЕ❗❗❗ В боте нет функции продления подписки. Повторную оплату производить только в случае, если бот напишет 'Продлить подписку' при нажатии кнопки 'Проверить'."
        )
    await message.answer(subscribe_text,  parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(inline_keyboard=[[pay_button, star_payment_button], [CHECK_PAYMENT_BUTTON], [MENU_BUTTON]]))
    
# Обработчик для оплаты звездами
@dp.callback_query(F.data == 'donate_star')
async def donate_star(callback: CallbackQuery):
    await send_invoice_handler(callback.message) 

# Запуск процесса поллинга новых апдейтов
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    init_db()  # Инициализируем базу данных
    asyncio.run(main())
