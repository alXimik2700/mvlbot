# первый блок
# Импорты библиотек
import asyncio
from dotenv import load_dotenv
import os
import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import aiohttp



# Переход к следующему блоку2
# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Переход к следующему блоку3
# Загрузка переменных окружения
dotenv_path = os.path.join(os.getcwd(), ".env")
if not os.path.exists(dotenv_path):
    logger.error(f"Файл .env не найден по пути: {dotenv_path}")
    exit(1)
else:
    logger.info(f"Файл .env найден: {dotenv_path}")
    load_dotenv(dotenv_path)

# Логирование переменных окружения
logger.info("Переменные окружения:")
for key in ["TELEGRAM_BOT_TOKEN", "CACHE_TIME"]:
    value = os.getenv(key)
    if value:
        logger.info(f"{key}: {'*' * len(value) if key == 'TELEGRAM_BOT_TOKEN' else value}")
    else:
        logger.warning(f"{key} не установлена.")

# Получение токена и времени кэширования
token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    logger.error("Токен бота не настроен. Установите переменную окружения TELEGRAM_BOT_TOKEN.")
    exit(1)

cache_time_env = os.getenv("CACHE_TIME")
try:
    CACHE_TIME_WORLD = int(cache_time_env or 3600)  # Время кэширования для мировых валют (1 час)
    CACHE_TIME_REGIONAL = 5 * CACHE_TIME_WORLD  # Время кэширования для региональных валют (5 часов)
    CACHE_TIME_CRYPTO = 8 * CACHE_TIME_WORLD  # Время кэширования для криптовалют (8 часов)
except ValueError:
    logger.error("Неверное значение для CACHE_TIME. Используется значение по умолчанию.")
    CACHE_TIME_WORLD = 3600
    CACHE_TIME_REGIONAL = 18000  # 5 часов
    CACHE_TIME_CRYPTO = 28800  # 8 часов


# Переход к следующему блоку4
# Глобальные переменные для хранения курсов валют
exchange_rates_world = {}
exchange_rates_regional = {}
exchange_rates_crypto = {}
last_update_world = 0
last_update_regional = 0
last_update_crypto = 0

# Глобальный ClientSession для минимизации создания новых HTTP-соединений
client_session = None


# Предварительная загрузка данных при старте бота
async def preload_exchange_rates():
    global client_session
    if client_session is None or (client_session and client_session.closed):
        client_session = aiohttp.ClientSession()
    logger.info("Предварительная загрузка курсов валют...")

    # Обновление курсов мировых валют
    await get_exchange_rates(force_update=True, cache_key="world_rates", cache_time=CACHE_TIME_WORLD)

    # Обновление курсов региональных валют
    await get_exchange_rates(force_update=True, cache_key="regional_rates", cache_time=CACHE_TIME_REGIONAL)

    # Обновление курсов криптовалют через CoinGecko
    await get_crypto_exchange_rates_with_fallback(force_update=True)


# Закрытие ClientSession при завершении работы
async def close_connector():
    global client_session
    if client_session and not client_session.closed:
        try:
            await client_session.close()
            logger.info("ClientSession успешно закрыт.")
        except Exception as e:
            logger.error(f"Ошибка при закрытии ClientSession: {e}")
    client_session = None


# Переход к следующему блоку5
# Список валют по материкам
EUROPE_CURRENCIES = {
    "EUR": "Евро 🇪🇺",
    "GBP": "Британский фунт стерлингов 🇬🇧",
    "CHF": "Швейцарский франк 🇨🇭",
    "RUB": "Российский рубль 🇷🇺",
    "UAH": "Украинская гривна 🇺🇦",
    "BYN": "Белорусский рубль 🇧🇾",
    "GEL": "Грузинский лари 🇬🇪",
    "AMD": "Армянский драм 🇦🇲",
    "MDL": "Молдавский лей 🇲🇩",
}

ASIA_CURRENCIES = {
    "JPY": "Японская иена 🇯🇵",
    "CNY": "Китайский юань 🇨🇳",
    "KZT": "Казахстанский тенге 🇰🇿",
    "AZN": "Азербайджанский манат 🇦🇿",
    "KGS": "Киргизский сом 🇰🇬",
    "TJS": "Таджикский сомони 🇹🇯",
    "TMT": "Туркменский манат 🇹🇲",
    "UZS": "Узбекский сум 🇺🇿",
    "INR": "Индийская рупия 🇮🇳",
    "IDR": "Индонезийская рупия 🇮🇩",
    "IRR": "Иранский риал 🇮🇷",
}

NORTH_AMERICA_CURRENCIES = {
    "USD": "Американский доллар 🇺🇸",
    "CAD": "Канадский доллар 🇨🇦",
    "MXN": "Мексиканское песо 🇲🇽",
}

SOUTH_AMERICA_CURRENCIES = {
    "BRL": "Бразильский реал 🇧🇷",
    "ARS": "Аргентинское песо 🇦🇷",
    "CLP": "Чилийское peso 🇨🇱",
}

AUSTRALIA_OCEANIA_CURRENCIES = {
    "AUD": "Австралийский доллар 🇦🇺",
    "NZD": "Новозеландский доллар 🇳🇿",
}

AFRICA_CURRENCIES = {
    "EGP": "Египетский фунт 🇪🇬",
    "NGN": "Нигерийская наира 🇳🇬",
}

WORLD_CURRENCIES = {
    "USD": "Американский доллар 🇺🇸",
    "EUR": "Евро 🇪🇺",
    "GBP": "Британский фунт стерлингов 🇬🇧",
    "JPY": "Японская иена 🇯🇵",
    "CHF": "Швейцарский франк 🇨🇭",
    "CNY": "Китайский юань 🇨🇳",
    "CAD": "Канадский доллар 🇨🇦",
    "AUD": "Австралийский доллар 🇦🇺",
}

REGIONAL_CURRENCIES = {
    "RUB": "Российский рубль 🇷🇺",
    "UAH": "Украинская гривна 🇺🇦",
    "BYN": "Белорусский рубль 🇧🇾",
    "KZT": "Казахстанский тенге 🇰🇿",
    "AZN": "Азербайджанский манат 🇦🇿",
    "AMD": "Армянский драм 🇦🇲",
    "GEL": "Грузинский лари 🇬🇪",
    "KGS": "Киргизский сом 🇰🇬",
    "MDL": "Молдавский лей 🇲🇩",
    "TJS": "Таджикский сомони 🇹🇯",
    "TMT": "Туркменский манат 🇹🇲",
    "UZS": "Узбекский сум 🇺🇿",
}

ALL_CURRENCIES = {
    **EUROPE_CURRENCIES,
    **ASIA_CURRENCIES,
    **NORTH_AMERICA_CURRENCIES,
    **SOUTH_AMERICA_CURRENCIES,
    **AUSTRALIA_OCEANIA_CURRENCIES,
    **AFRICA_CURRENCIES,
    **WORLD_CURRENCIES,
    **REGIONAL_CURRENCIES,
}


# Безопасное редактирование сообщения
async def safe_edit_message(query, text, reply_markup):
    if query.message.text != text or query.message.reply_markup != reply_markup:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        logger.info("Сообщение не изменилось, обновление не требуется.")


# Закрытие ClientSession
async def close_connector():
    global client_session
    if client_session and not client_session.closed:
        try:
            await client_session.close()
            logger.info("ClientSession успешно закрыт.")
        except Exception as e:
            logger.error(f"Ошибка при закрытии ClientSession: {e}")
    client_session = None

# Переход к следующему блоку6
# Функция для получения курсов валют
async def get_exchange_rates(force_update=False, cache_key="world_rates", cache_time=CACHE_TIME_WORLD):
    """
    Получает курсы валют из API с возможностью использования закэшированных данных.
    Поддерживает как фиатные валюты, так и криптовалюты.
    """
    global exchange_rates_world, exchange_rates_regional, last_update_world, last_update_regional, client_session
    current_time = time.time()

    # Определяем используемые глобальные переменные в зависимости от ключа кэша
    rates_dict = {
        "world_rates": [exchange_rates_world, last_update_world],
        "regional_rates": [exchange_rates_regional, last_update_regional]
    }
    rates, last_update = rates_dict.get(cache_key, (None, None))

    # Проверяем, можно ли использовать закэшированные данные
    if not force_update and last_update and (current_time - last_update < cache_time):
        logger.info(f"Используются закэшированные курсы ({cache_key}).")
        return rates

    # Инициализация ClientSession, если она не создана или закрыта
    if not client_session or client_session.closed:
        client_session = aiohttp.ClientSession()

    # URL для запроса курсов валют
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        async with client_session.get(url) as response:
            if response.status != 200:
                logger.error(f"Ошибка при запросе к API ({url}): {response.status}")
                return None
            data = await response.json()
            new_rates = data.get("rates", {})

            # Обновляем глобальные переменные в зависимости от ключа кэша
            if cache_key == "world_rates":
                exchange_rates_world = new_rates
                last_update_world = current_time
            elif cache_key == "regional_rates":
                exchange_rates_regional = new_rates
                last_update_regional = current_time

            logger.info(f"Курсы валют обновлены ({cache_key}).")
            return new_rates
    except Exception as e:
        logger.error(f"Ошибка при запросе к API ({url}): {e}")
        return None


# Функция для получения курсов криптовалют через CoinGecko
async def get_crypto_exchange_rates_coingecko(force_update=False):
    """
    Получает курсы криптовалют через CoinGecko API.
    """
    global client_session, exchange_rates_crypto, last_update_crypto

    current_time = time.time()

    # Проверяем, можно ли использовать закэшированные данные
    if not force_update and last_update_crypto and (current_time - last_update_crypto < CACHE_TIME_CRYPTO):
        logger.info("Используются закэшированные курсы криптовалют.")
        return exchange_rates_crypto

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum,binancecoin,ripple,cardano",
        "vs_currencies": "usd",
    }

    try:
        async with client_session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                new_rates = {
                    "BTC": data.get("bitcoin", {}).get("usd"),
                    "ETH": data.get("ethereum", {}).get("usd"),
                    "BNB": data.get("binancecoin", {}).get("usd"),
                    "XRP": data.get("ripple", {}).get("usd"),
                    "ADA": data.get("cardano", {}).get("usd"),
                }
                if all(new_rates.values()):
                    exchange_rates_crypto = new_rates
                    last_update_crypto = current_time
                    logger.info("Курсы криптовалют успешно обновлены через CoinGecko.")
                    return new_rates
                else:
                    logger.error("Некорректные данные от CoinGecko.")
            else:
                logger.error(f"Ошибка при запросе к CoinGecko: {response.status}")
    except Exception as e:
        logger.error(f"Ошибка при запросе к CoinGecko: {e}")
    return None


# Функция для получения курсов криптовалют через CoinMarketCap
async def get_crypto_exchange_rates_coinmarketcap(force_update=False):
    """
    Получает курсы криптовалют через CoinMarketCap API.
    """
    global client_session, exchange_rates_crypto, last_update_crypto

    current_time = time.time()

    # Проверяем, можно ли использовать закэшированные данные
    if not force_update and last_update_crypto and (current_time - last_update_crypto < CACHE_TIME_CRYPTO):
        logger.info("Используются закэшированные курсы криптовалют.")
        return exchange_rates_crypto

    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    params = {
        "symbol": "BTC,ETH,BNB,XRP,ADA",
        "convert": "USD",
    }
    headers = {
        "X-CMC_PRO_API_KEY": os.getenv("COINMARKETCAP_API_KEY"),
    }

    try:
        async with client_session.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                quotes = data.get("data", {})
                new_rates = {
                    "BTC": quotes.get("BTC", {}).get("quote", {}).get("USD", {}).get("price"),
                    "ETH": quotes.get("ETH", {}).get("quote", {}).get("USD", {}).get("price"),
                    "BNB": quotes.get("BNB", {}).get("quote", {}).get("USD", {}).get("price"),
                    "XRP": quotes.get("XRP", {}).get("quote", {}).get("USD", {}).get("price"),
                    "ADA": quotes.get("ADA", {}).get("quote", {}).get("USD", {}).get("price"),
                }
                if all(new_rates.values()):
                    exchange_rates_crypto = new_rates
                    last_update_crypto = current_time
                    logger.info("Курсы криптовалют успешно обновлены через CoinMarketCap.")
                    return new_rates
                else:
                    logger.error("Некорректные данные от CoinMarketCap.")
            else:
                logger.error(f"Ошибка при запросе к CoinMarketCap: {response.status}")
    except Exception as e:
        logger.error(f"Ошибка при запросе к CoinMarketCap: {e}")
    return None


# Функция для получения курсов криптовалют с fallback-логикой
async def get_crypto_exchange_rates_with_fallback(force_update=False):
    """
    Получает курсы криптовалют через несколько источников с возможностью самозамены.
    """
    sources = [
        {"func": get_crypto_exchange_rates_coingecko, "name": "CoinGecko"},
        {"func": get_crypto_exchange_rates_coinmarketcap, "name": "CoinMarketCap"},
    ]

    for source in sources:
        try:
            rates = await source["func"](force_update=True)
            if rates:
                logger.info(f"Курсы криптовалют успешно получены через {source['name']}.")
                return rates
            else:
                logger.warning(f"Некорректные данные от {source['name']}.")
        except Exception as e:
            logger.error(f"Ошибка при запросе к {source['name']}: {e}")

    logger.error("Не удалось получить курсы криптовалют ни из одного источника.")
    return None

# Переход к следующему блоку7
# Создание главного меню
def create_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🌍 Европа 🇪🇺", callback_data="europe_currencies")],
        [InlineKeyboardButton("🌏 Азия 🇯🇵", callback_data="asia_currencies")],
        [InlineKeyboardButton("NORTH Америка 🇺🇸", callback_data="north_america_currencies")],
        [InlineKeyboardButton("SOUTH Америка 🇧🇷", callback_data="south_america_currencies")],
        [InlineKeyboardButton("🇦🇺 Австралия и Океания 🌊", callback_data="australia_oceania_currencies")],
        [InlineKeyboardButton("🌍 Африка 🇪🇬", callback_data="africa_currencies")],
        [InlineKeyboardButton("₿ Криптовалюты ⚡", callback_data="crypto_currencies")],
        [InlineKeyboardButton("🔍 Конвертировать валюту 💱", callback_data="convert_currency")],
        [InlineKeyboardButton("🔄 Обновить курсы 🔄", callback_data="update_rates")],
    ]
    return InlineKeyboardMarkup(keyboard)


# Создание кнопки "Назад"
def create_back_keyboard():
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="start")]]
    return InlineKeyboardMarkup(keyboard)


# Создание клавиатуры с доступными валютами для конвертации
def create_currency_selection_keyboard(currencies, step):
    """
    Создает клавиатуру с доступными валютами для выбора при конвертации.

    :param currencies: Список доступных валют (включая криптовалюты).
    :param step: Текущий шаг выбора ('from' - исходная валюта, 'to' - целевая валюта, 'from_crypto' - исходная криптовалюта, 'to_crypto' - целевая криптовалюта).
    :return: InlineKeyboardMarkup объект.
    """
    keyboard = []
    for currency in currencies:
        flag = get_currency_flag(currency)  # Получаем флаг или символ для валюты
        keyboard.append([InlineKeyboardButton(f"{currency} {flag}", callback_data=f"{step}_{currency}")])

    # Добавляем кнопку "Назад"
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
    return InlineKeyboardMarkup(keyboard)


# Вспомогательная функция для получения флага или символа валюты
def get_currency_flag(currency):
    """
    Возвращает флаг или символ для указанной валюты.

    :param currency: Код валюты
    :return: Строка с флагом или символом валюты
    """
    flags = {
        "EUR": "🇪🇺",  # Евро
        "GBP": "🇬🇧",  # Британский фунт стерлингов
        "JPY": "🇯🇵",  # Японская иена
        "CHF": "🇨🇭",  # Швейцарский франк
        "CNY": "🇨🇳",  # Китайский юань
        "CAD": "🇨🇦",  # Канадский доллар
        "AUD": "🇦🇺",  # Австралийский доллар
        "USD": "🇺🇸",  # Американский доллар
        "RUB": "🇷🇺",  # Российский рубль
        "UAH": "🇺🇦",  # Украинская гривна
        "BYN": "🇧🇾",  # Белорусский рубль
        "KZT": "🇰🇿",  # Казахстанский тенге
        "AZN": "🇦🇿",  # Азербайджанский манат
        "AMD": "🇦🇲",  # Армянский драм
        "GEL": "🇬🇪",  # Грузинский лари
        "KGS": "🇰🇬",  # Киргизский сом
        "MDL": "🇲🇩",  # Молдавский лей
        "TJS": "🇹🇯",  # Таджикский сомони
        "TMT": "🇹🇲",  # Туркменский манат
        "UZS": "🇺🇿",  # Узбекский сум
        "INR": "🇮🇳",  # Индийская рупия
        "IDR": "🇮🇩",  # Индонезийская рупия
        "IRR": "🇮🇷",  # Иранский риал
        "BRL": "🇧🇷",  # Бразильский реал
        "NZD": "🇳🇿",  # Новозеландский доллар
        "EGP": "🇪🇬",  # Египетский фунт
        "NGN": "🇳🇬",  # Нигерийская наира
        "ARS": "🇦🇷",  # Аргентинское песо
        "MXN": "🇲🇽",  # Мексиканское песо
        "CLP": "🇨🇱",  # Чилийское peso

        # Криптовалюты
        "BTC": "₿",  # Bitcoin
        "ETH": "Ξ",  # Ethereum
        "BNB": "💎",  # Binance Coin
        "XRP": "✨",  # Ripple
        "ADA": "♠️",  # Cardano
    }
    return flags.get(currency, "")  # Возвращаем пустую строку, если флаг не найден


# Переход к следующему блоку8
# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /start.
    """
    user = update.effective_user
    logger.info(f"Пользователь {user.id} ({user.username}) вызвал команду /start")

    # Приветствие на двух языках
    await update.message.reply_text(
        "🇬🇧 Hello! I'm your currency converter bot. How can I assist you today?\n\n"
        "🇷🇺 Добро пожаловать в бота-конвертер валют!\n\n"
        "I can show you current exchange rates and help you convert one currency to another.\n"
        "Я могу показывать актуальные курсы валют и помогать вам конвертировать одну валюту в другую.\n\n"
        "Choose an action / Выберите действие:",
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard(),
    )


# Переход к следующему блоку9
# Обработка нажатий на кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем получение запроса от Telegram

    try:
        if query.data == "start":
            # Пользователь вернулся в главное меню
            logger.info(f"Пользователь {query.from_user.id} ({query.from_user.username}) вернулся в главное меню")
            message = "Главное меню\nВыберите действие:"
            await safe_edit_message(query, message, create_main_menu_keyboard())
            context.user_data.clear()  # Очищаем данные пользователя при возврате в главное меню

        elif query.data == "update_rates":
            # Обновление курсов валют
            logger.info(f"Пользователь {query.from_user.id} ({query.from_user.username}) выбрал 'Обновить курсы'")
            rates = await get_crypto_exchange_rates_with_fallback(force_update=True)
            if rates:
                message = "Курсы валют успешно обновлены!"
            else:
                message = "Не удалось обновить курсы валют. Попробуйте позже."
            await safe_edit_message(query, message, create_main_menu_keyboard())

        elif query.data in [
            "europe_currencies", "asia_currencies",
            "north_america_currencies", "south_america_currencies",
            "australia_oceania_currencies", "africa_currencies"
        ]:
            # Обработка выбора региональных валют
            region_map = {
                "europe_currencies": (EUROPE_CURRENCIES, "Европы"),
                "asia_currencies": (ASIA_CURRENCIES, "Азии"),
                "north_america_currencies": (NORTH_AMERICA_CURRENCIES, "Северной Америки"),
                "south_america_currencies": (SOUTH_AMERICA_CURRENCIES, "Южной Америки"),
                "australia_oceania_currencies": (AUSTRALIA_OCEANIA_CURRENCIES, "Австралии и Океании"),
                "africa_currencies": (AFRICA_CURRENCIES, "Африки"),
            }

            if query.data in region_map:
                region_currencies, region_name = region_map[query.data]
                await handle_region_currencies(query, region_currencies, region_name)
            else:
                logger.error(f"Неизвестный регион: {query.data}")
                message = "Произошла ошибка. Пожалуйста, начните заново."
                await safe_edit_message(query, message, create_main_menu_keyboard())

        elif query.data == "crypto_currencies":
            # Обработка выбора криптовалют
            logger.info(f"Пользователь {query.from_user.id} ({query.from_user.username}) выбрал 'Криптовалюты'")
            rates = await get_crypto_exchange_rates_with_fallback()
            if rates:
                crypto_currencies = {
                    "BTC": "Bitcoin ₿",
                    "ETH": "Ethereum Ξ",
                    "BNB": "Binance Coin 💎",
                    "XRP": "Ripple ✨",
                    "ADA": "Cardano ♠️",
                }
                message = "Текущие курсы популярных криптовалют:\n\n"
                for currency, name in crypto_currencies.items():
                    message += f"{name} ({currency}) = {rates.get(currency, '— данные недоступны'):.2f} USD\n"

                keyboard = []
                for currency in crypto_currencies.keys():
                    emoji = {"BTC": "₿", "ETH": "Ξ", "BNB": "💎", "XRP": "✨", "ADA": "♠️"}.get(currency, "")
                    keyboard.append([InlineKeyboardButton(f"{currency} {emoji}", callback_data=f"convert_from_crypto_{currency}")])

                keyboard.append([InlineKeyboardButton("🔍 Конвертировать крипту", callback_data="convert_crypto_currency")])
                keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="start")])

                await safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))
            else:
                message = "Не удалось получить курсы криптовалют. Попробуйте позже."
                await safe_edit_message(query, message, create_main_menu_keyboard())

        elif query.data == "convert_currency":
            # Начало конвертации обычных валют
            logger.info(f"Пользователь {query.from_user.id} ({query.from_user.username}) выбрал 'Конвертировать валюту'")
            rates = await get_exchange_rates(cache_key="world_rates", cache_time=CACHE_TIME_WORLD)
            if rates:
                message = "Выберите исходную валюту:"
                available_currencies = list(ALL_CURRENCIES.keys()) + ["BTC", "ETH", "BNB", "XRP", "ADA"]
                await safe_edit_message(query, message, create_currency_selection_keyboard(available_currencies, step="from"))
                context.user_data["step"] = "select_from_currency"
            else:
                message = "Не удалось получить курсы валют. Попробуйте позже."
                await safe_edit_message(query, message, create_main_menu_keyboard())

        elif query.data == "convert_crypto_currency":
            # Начало конвертации криптовалют
            logger.info(f"Пользователь {query.from_user.id} ({query.from_user.username}) выбрал 'Конвертировать криптовалюту'")
            rates = await get_crypto_exchange_rates_with_fallback()
            if rates:
                message = "Выберите исходную криптовалюту:"
                available_currencies = ["BTC", "ETH", "BNB", "XRP", "ADA"]
                await safe_edit_message(query, message, create_currency_selection_keyboard(available_currencies, step="from_crypto"))
                context.user_data["step"] = "select_from_crypto_currency"
            else:
                message = "Не удалось получить курсы криптовалют. Попробуйте позже."
                await safe_edit_message(query, message, create_main_menu_keyboard())

        elif query.data.startswith("from_"):
            # Пользователь выбрал исходную валюту
            from_currency = query.data.split("_")[1]
            context.user_data["from_currency"] = from_currency
            logger.info(f"Пользователь {query.from_user.id} ({query.from_user.username}) выбрал исходную валюту: {from_currency}")

            message = f"Вы выбрали исходную валюту: {from_currency}\n\nВыберите целевую валюту:"
            available_currencies = [c for c in list(ALL_CURRENCIES.keys()) + ["BTC", "ETH", "BNB", "XRP", "ADA"] if c != from_currency]
            await safe_edit_message(query, message, create_currency_selection_keyboard(available_currencies, step="to"))
            context.user_data["step"] = "select_to_currency"

        elif query.data.startswith("from_crypto_"):
            # Пользователь выбрал исходную криптовалюту
            from_currency = query.data.split("_")[2]
            context.user_data["from_currency"] = from_currency
            logger.info(f"Пользователь {query.from_user.id} ({query.from_user.username}) выбрал исходную криптовалюту: {from_currency}")

            message = f"Вы выбрали исходную криптовалюту: {from_currency}\n\nВыберите целевую валюту:"
            available_currencies = list(ALL_CURRENCIES.keys()) + ["BTC", "ETH", "BNB", "XRP", "ADA"]
            await safe_edit_message(query, message, create_currency_selection_keyboard(available_currencies, step="to_crypto"))
            context.user_data["step"] = "select_to_currency_crypto"

        elif query.data.startswith("to_"):
            # Пользователь выбрал целевую валюту
            to_currency = query.data.split("_")[1]
            context.user_data["to_currency"] = to_currency
            logger.info(f"Пользователь {query.from_user.id} ({query.from_user.username}) выбрал целевую валюту: {to_currency}")

            from_currency = context.user_data.get("from_currency")
            if not from_currency:
                message = "Ошибка: Не выбрана исходная валюта."
                await safe_edit_message(query, message, create_main_menu_keyboard())
                return

            message = f"Вы выбрали конвертацию из {from_currency} в {to_currency}.\n\nВведите сумму для конвертации:"
            await safe_edit_message(query, message, create_back_keyboard())
            context.user_data["step"] = "enter_amount"

        elif query.data.startswith("to_crypto_"):
            # Пользователь выбрал целевую валюту для криптовалют
            to_currency = query.data.split("_")[2]
            context.user_data["to_currency"] = to_currency
            logger.info(f"Пользователь {query.from_user.id} ({query.from_user.username}) выбрал целевую валюту: {to_currency}")

            from_currency = context.user_data.get("from_currency")
            if not from_currency:
                message = "Ошибка: Не выбрана исходная валюта."
                await safe_edit_message(query, message, create_main_menu_keyboard())
                return

            message = f"Вы выбрали конвертацию из {from_currency} в {to_currency}.\n\nВведите сумму для конвертации:"
            await safe_edit_message(query, message, create_back_keyboard())
            context.user_data["step"] = "enter_amount_crypto"

        elif query.data == "back":
            # Возвращение назад
            current_step = context.user_data.get("step")
            if current_step == "select_to_currency":
                message = "Выберите исходную валюту:"
                available_currencies = list(ALL_CURRENCIES.keys()) + ["BTC", "ETH", "BNB", "XRP", "ADA"]
                await safe_edit_message(query, message, create_currency_selection_keyboard(available_currencies, step="from"))
                context.user_data["step"] = "select_from_currency"
            elif current_step == "enter_amount":
                from_currency = context.user_data.get("from_currency")
                if from_currency:
                    message = f"Вы выбрали исходную валюту: {from_currency}\n\nВыберите целевую валюту:"
                    available_currencies = [c for c in list(ALL_CURRENCIES.keys()) + ["BTC", "ETH", "BNB", "XRP", "ADA"] if c != from_currency]
                    await safe_edit_message(query, message, create_currency_selection_keyboard(available_currencies, step="to"))
                    context.user_data["step"] = "select_to_currency"
                else:
                    message = "Выберите исходную валюту:"
                    available_currencies = list(ALL_CURRENCIES.keys()) + ["BTC", "ETH", "BNB", "XRP", "ADA"]
                    await safe_edit_message(query, message, create_currency_selection_keyboard(available_currencies, step="from"))
                    context.user_data["step"] = "select_from_currency"
            elif current_step == "select_to_currency_crypto":
                message = "Выберите исходную криптовалюту:"
                available_currencies = ["BTC", "ETH", "BNB", "XRP", "ADA"]
                await safe_edit_message(query, message, create_currency_selection_keyboard(available_currencies, step="from_crypto"))
                context.user_data["step"] = "select_from_crypto_currency"
            elif current_step == "enter_amount_crypto":
                from_currency = context.user_data.get("from_currency")
                if from_currency:
                    message = f"Вы выбрали исходную криптовалюту: {from_currency}\n\nВыберите целевую валюту:"
                    available_currencies = list(ALL_CURRENCIES.keys()) + ["BTC", "ETH", "BNB", "XRP", "ADA"]
                    await safe_edit_message(query, message, create_currency_selection_keyboard(available_currencies, step="to_crypto"))
                    context.user_data["step"] = "select_to_currency_crypto"
                else:
                    message = "Выберите исходную криптовалюту:"
                    available_currencies = ["BTC", "ETH", "BNB", "XRP", "ADA"]
                    await safe_edit_message(query, message, create_currency_selection_keyboard(available_currencies, step="from_crypto"))
                    context.user_data["step"] = "select_from_crypto_currency"
            else:
                message = "Главное меню\nВыберите действие:"
                await safe_edit_message(query, message, create_main_menu_keyboard())

    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки: {e}")
        message = "Произошла ошибка. Пожалуйста, попробуйте еще раз."
        await safe_edit_message(query, message, create_main_menu_keyboard())


# Обработка текстового ввода для конвертации
async def convert_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        current_step = context.user_data.get("step")
        if current_step not in ["enter_amount", "enter_amount_crypto"]:
            message = "Ошибка: Неверный шаг. Пожалуйста, начните заново."
            await update.message.reply_text(
                text=message,
                parse_mode="HTML",
                reply_markup=create_main_menu_keyboard(),
            )
            return

        logger.info(f"Пользователь {update.effective_user.id} ({update.effective_user.username}) ввел сумму для конвертации")

        # Парсим введенную сумму
        try:
            amount = float(update.message.text.strip())
            if amount <= 0:
                message = "Сумма должна быть больше нуля."
                await update.message.reply_text(message, reply_markup=create_back_keyboard())
                return
        except ValueError:
            message = "Некорректный ввод. Введите число."
            await update.message.reply_text(message, reply_markup=create_back_keyboard())
            return

        from_currency = context.user_data.get("from_currency")
        to_currency = context.user_data.get("to_currency")

        if not from_currency or not to_currency:
            message = "Ошибка: Не выбрана исходная или целевая валюта."
            await update.message.reply_text(message, reply_markup=create_main_menu_keyboard())
            return

        # Получаем актуальные курсы
        rates = {}
        if from_currency in ALL_CURRENCIES or to_currency in ALL_CURRENCIES:
            rates.update(await get_exchange_rates(force_update=True, cache_key="world_rates", cache_time=CACHE_TIME_WORLD))
        if from_currency in ["BTC", "ETH", "BNB", "XRP", "ADA"] or to_currency in ["BTC", "ETH", "BNB", "XRP", "ADA"]:
            rates.update(await get_crypto_exchange_rates_with_fallback(force_update=True))

        if not rates:
            message = "Не удалось получить курсы валют. Попробуйте позже."
            await update.message.reply_text(message, reply_markup=create_main_menu_keyboard())
            return

        # Выполняем конвертацию
        rate_from = rates.get(from_currency)
        rate_to = rates.get(to_currency)

        # Логика для конвертации из фиата в крипту
        if from_currency in ALL_CURRENCIES and to_currency in ["BTC", "ETH", "BNB", "XRP", "ADA"]:
            # Конвертируем из фиата в USD
            usd_rate = rates.get("USD", 1)  # Если исходная валюта USD, курс = 1
            if from_currency != "USD":
                rate_from = rates.get(from_currency, None)
                if rate_from is None:
                    message = f"Не найден курс для {from_currency}."
                    await update.message.reply_text(message, reply_markup=create_main_menu_keyboard())
                    return
                usd_amount = amount / rate_from  # Переводим в USD
            else:
                usd_amount = amount  # Если исходная валюта USD

            # Конвертируем из USD в крипту
            crypto_rate = rates.get(to_currency, None)
            if crypto_rate is None:
                message = f"Не найден курс для {to_currency}."
                await update.message.reply_text(message, reply_markup=create_main_menu_keyboard())
                return
            result = usd_amount / crypto_rate  # Переводим в крипту

        # Логика для других типов конвертации
        else:
            if from_currency in ["BTC", "ETH", "BNB", "XRP", "ADA"]:
                rate_from = 1 / rate_from if rate_from else None
            if to_currency in ["BTC", "ETH", "BNB", "XRP", "ADA"]:
                rate_to = 1 / rate_to if rate_to else None

            if rate_from is None or rate_to is None:
                message = "Не удалось выполнить конвертацию. Убедитесь, что выбраны корректные валюты."
                await update.message.reply_text(message, reply_markup=create_main_menu_keyboard())
                return

            result = (amount * rate_from) / rate_to if rate_to else None

        if result is not None:
            message = f"{amount:.2f} {from_currency} = {result:.8f} {to_currency}"
        else:
            message = "Не удалось выполнить конвертацию."

        await update.message.reply_text(message, reply_markup=create_main_menu_keyboard())

    except Exception as e:
        logger.error(f"Ошибка при конвертации валют: {e}")
        message = "Произошла ошибка. Пожалуйста, попробуйте еще раз."
        await update.message.reply_text(message, reply_markup=create_main_menu_keyboard())


# Переход к следующему блоку10
# Функция для получения курсов валют с возможностью использования закэшированных данных
async def get_exchange_rates(force_update=False, cache_key="world_rates", cache_time=CACHE_TIME_WORLD):
    """
    Получает курсы валют из API с возможностью использования закэшированных данных.
    """
    global exchange_rates_world, exchange_rates_regional, last_update_world, last_update_regional, client_session
    current_time = time.time()

    # Определяем используемые глобальные переменные в зависимости от ключа кэша
    rates_dict = {
        "world_rates": [exchange_rates_world, last_update_world],
        "regional_rates": [exchange_rates_regional, last_update_regional]
    }
    rates, last_update = rates_dict.get(cache_key, (None, None))

    # Проверяем, можно ли использовать закэшированные данные
    if not force_update and last_update and (current_time - last_update < cache_time):
        logger.info(f"Используются закэшированные курсы ({cache_key}).")
        return rates

    # Инициализация ClientSession, если она не создана или закрыта
    if not client_session or client_session.closed:
        client_session = aiohttp.ClientSession()

    # URL для запроса курсов валют
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        async with client_session.get(url) as response:
            if response.status != 200:
                logger.error(f"Ошибка при запросе к API ({url}): {response.status}")
                return None
            data = await response.json()
            new_rates = data.get("rates", {})

            # Обновляем глобальные переменные в зависимости от ключа кэша
            if cache_key == "world_rates":
                exchange_rates_world = new_rates
                last_update_world = current_time
            elif cache_key == "regional_rates":
                exchange_rates_regional = new_rates
                last_update_regional = current_time

            logger.info(f"Курсы валют обновлены ({cache_key}).")
            return new_rates
    except Exception as e:
        logger.error(f"Ошибка при запросе к API ({url}): {e}")
        return None


# Универсальная функция для обработки регионов
async def handle_region_currencies(query, region_currencies, region_name):
    """
    Отображает курсы валют для выбранного региона.
    """
    logger.info(f"Пользователь {query.from_user.id} ({query.from_user.username}) выбрал 'Валюты {region_name}'")

    # Получаем актуальные курсы валют
    rates = await get_exchange_rates(cache_key="world_rates", cache_time=CACHE_TIME_WORLD)
    if not rates:
        message = "Не удалось получить курсы валют. Попробуйте позже."
        await safe_edit_message(query, message, create_main_menu_keyboard())
        return

    # Формируем сообщение с курсами валют
    message = f"Текущие курсы валют {region_name}:\n\n"
    for currency, name in region_currencies.items():
        rate = rates.get(currency, "— данные недоступны")
        message += f"{name} ({currency}) = {rate:.2f} USD\n"

    # Создаем клавиатуру с кнопками для каждой валюты
    keyboard = []
    for currency in region_currencies.keys():
        flag = get_currency_flag(currency)  # Получаем флаг для валюты
        keyboard.append([InlineKeyboardButton(f"{currency} {flag}", callback_data=f"convert_from_{currency}")])

    # Добавляем кнопки "Конвертировать" и "Назад"
    keyboard.append([InlineKeyboardButton("🔍 Конвертировать", callback_data="convert_currency")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="start")])

    # Отправляем сообщение пользователю
    await safe_edit_message(query, message, InlineKeyboardMarkup(keyboard))


# Обработка текстового ввода для конвертации
async def convert_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        current_step = context.user_data.get("step")
        if current_step not in ["enter_amount", "enter_amount_crypto"]:
            message = "Ошибка: Неверный шаг. Пожалуйста, начните заново."
            await update.message.reply_text(
                text=message,
                parse_mode="HTML",
                reply_markup=create_main_menu_keyboard(),
            )
            return

        logger.info(f"Пользователь {update.effective_user.id} ({update.effective_user.username}) ввел сумму для конвертации")

        # Парсим введенную сумму
        try:
            amount = float(update.message.text.strip())
            if amount <= 0:
                message = "Сумма должна быть положительным числом. Пожалуйста, попробуйте снова."
                await update.message.reply_text(
                    text=message,
                    parse_mode="HTML",
                    reply_markup=create_back_keyboard(),
                )
                return
        except ValueError:
            message = "Ошибка: Введите корректное число."
            await update.message.reply_text(
                text=message,
                parse_mode="HTML",
                reply_markup=create_back_keyboard(),
            )
            return

        # Получаем исходную и целевую валюты
        from_currency = context.user_data.get("from_currency")
        to_currency = context.user_data.get("to_currency")
        if not from_currency or not to_currency:
            message = "Ошибка: Не выбраны валюты для конвертации."
            await update.message.reply_text(
                text=message,
                parse_mode="HTML",
                reply_markup=create_main_menu_keyboard(),
            )
            return

        # Конвертация обычных валют
        if from_currency in ALL_CURRENCIES and to_currency in ALL_CURRENCIES:
            rates = await get_exchange_rates(cache_key="world_rates", cache_time=CACHE_TIME_WORLD)
            if not rates:
                message = "Не удалось получить курсы валют. Попробуйте позже."
                await update.message.reply_text(
                    text=message,
                    parse_mode="HTML",
                    reply_markup=create_main_menu_keyboard(),
                )
                return

            from_rate = rates.get(from_currency)
            to_rate = rates.get(to_currency)
            if not from_rate or not to_rate:
                message = "Ошибка: Не найдены курсы для выбранных валют."
                await update.message.reply_text(
                    text=message,
                    parse_mode="HTML",
                    reply_markup=create_main_menu_keyboard(),
                )
                return

            converted_amount = (amount / from_rate) * to_rate

        # Конвертация криптовалют
        elif from_currency in ["BTC", "ETH", "BNB", "XRP", "ADA"] or to_currency in ["BTC", "ETH", "BNB", "XRP", "ADA"]:
            crypto_rates = await get_crypto_exchange_rates_with_fallback()
            if not crypto_rates:
                message = "Не удалось получить курсы криптовалют. Попробуйте позже."
                await update.message.reply_text(
                    text=message,
                    parse_mode="HTML",
                    reply_markup=create_main_menu_keyboard(),
                )
                return

            from_rate = crypto_rates.get(from_currency) if from_currency in crypto_rates else None
            to_rate = crypto_rates.get(to_currency) if to_currency in crypto_rates else None

            if not from_rate or not to_rate:
                message = "Ошибка: Не найдены курсы для выбранных криптовалют."
                await update.message.reply_text(
                    text=message,
                    parse_mode="HTML",
                    reply_markup=create_main_menu_keyboard(),
                )
                return

            # Конвертация через USD
            if from_currency in crypto_rates and to_currency in ALL_CURRENCIES:
                exchange_rates = await get_exchange_rates(cache_key="world_rates", cache_time=CACHE_TIME_WORLD)
                if not exchange_rates:
                    message = "Не удалось получить курсы валют. Попробуйте позже."
                    await update.message.reply_text(
                        text=message,
                        parse_mode="HTML",
                        reply_markup=create_main_menu_keyboard(),
                    )
                    return

                to_rate_usd = exchange_rates.get(to_currency)
                if not to_rate_usd:
                    message = f"Ошибка: Не найден курс для {to_currency}."
                    await update.message.reply_text(
                        text=message,
                        parse_mode="HTML",
                        reply_markup=create_main_menu_keyboard(),
                    )
                    return

                converted_amount = (amount * from_rate) / to_rate_usd

            elif from_currency in ALL_CURRENCIES and to_currency in crypto_rates:
                exchange_rates = await get_exchange_rates(cache_key="world_rates", cache_time=CACHE_TIME_WORLD)
                if not exchange_rates:
                    message = "Не удалось получить курсы валют. Попробуйте позже."
                    await update.message.reply_text(
                        text=message,
                        parse_mode="HTML",
                        reply_markup=create_main_menu_keyboard(),
                    )
                    return

                from_rate_usd = exchange_rates.get(from_currency)
                if not from_rate_usd:
                    message = f"Ошибка: Не найден курс для {from_currency}."
                    await update.message.reply_text(
                        text=message,
                        parse_mode="HTML",
                        reply_markup=create_main_menu_keyboard(),
                    )
                    return

                converted_amount = (amount / from_rate_usd) * to_rate

            elif from_currency in crypto_rates and to_currency in crypto_rates:
                converted_amount = (amount * from_rate) / to_rate

        # Отправляем результат пользователю
        message = (
            f"Результат конвертации:\n\n"
            f"{amount:.2f} {from_currency} = {converted_amount:.2f} {to_currency}"
        )
        await update.message.reply_text(
            text=message,
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard(),
        )

    except Exception as e:
        logger.error(f"Ошибка при конвертации: {e}")
        message = "Произошла ошибка при конвертации. Пожалуйста, попробуйте еще раз."
        await update.message.reply_text(
            text=message,
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard(),
        )


# Переход к следующему блоку11
# Регистрация обработчиков
async def register_handlers(application):
    """
    Регистрация всех обработчиков для бота.
    """
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))

    # Обработчик числового ввода для конвертации обычных валют
    application.add_handler(
        MessageHandler(filters.Regex(r'^\d+(\.\d+)?$'), convert_currency)
    )

    # Обработчики кнопок
    application.add_handler(CallbackQueryHandler(button_handler))


# Точка входа
async def close_connector():
    global client_session
    if client_session and not client_session.closed:
        try:
            await client_session.close()
            logger.info("ClientSession успешно закрыт.")
        except Exception as e:
            logger.error(f"Ошибка при закрытии ClientSession: {e}")
    client_session = None


async def shutdown():
    try:
        await close_connector()
        logger.info("Бот остановлен.")
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")


def main():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        application = Application.builder().token(token).build()

        # Предварительная загрузка данных
        loop.run_until_complete(preload_exchange_rates())

        # Регистрация обработчиков
        loop.run_until_complete(register_handlers(application))

        # Запуск бота
        logger.info("Бот запущен. Нажмите Ctrl+C для остановки.")
        loop.run_until_complete(application.run_polling(close_loop=False))
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        if 'loop' in locals() and loop.is_running():
            tasks = asyncio.all_tasks(loop)
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.run_until_complete(shutdown())
            if application:
                loop.run_until_complete(application.shutdown())
            loop.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        asyncio.run(shutdown())