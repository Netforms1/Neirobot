import logging
import os
from collections import defaultdict, deque
from typing import Deque, Dict

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))

BASE_PROMPT = (
    "Ты — Нейробот, универсальный ИИ-помощник. Отвечай чётко, по делу, "
    "на языке пользователя. Если вопрос неоднозначный — задай уточняющий вопрос."
)

MODES: Dict[str, Dict[str, str]] = {
    "Программирование": {
        "prompt": "Ты — опытный программист. Помогай с кодом, отладкой, "
                  "архитектурой. Давай готовые примеры кода с пояснениями.",
        "greeting": "Режим: Программирование. Опиши задачу, вставь код или "
                    "ошибку — помогу разобраться.",
    },
    "Тексты": {
        "prompt": "Ты — редактор и копирайтер. Помогай писать, редактировать, "
                  "улучшать тексты любого стиля и формата.",
        "greeting": "Режим: Тексты. Напиши, какой текст нужен (или вставь "
                    "существующий для правки).",
    },
    "Перевод": {
        "prompt": "Ты — профессиональный переводчик. Переводи присланный "
                  "текст. Если язык перевода не указан — спрашивай.",
        "greeting": "Режим: Перевод. Пришли текст и укажи язык, на который "
                    "перевести.",
    },
    "Идеи": {
        "prompt": "Ты — генератор идей и брейншторм-партнёр. Предлагай "
                  "креативные, разнообразные и применимые варианты.",
        "greeting": "Режим: Идеи. Опиши задачу — накидаю варианты.",
    },
    "Математика": {
        "prompt": "Ты — преподаватель математики. Решай задачи пошагово, "
                  "объясняй каждый шаг, проверяй вычисления.",
        "greeting": "Режим: Математика. Пришли задачу или пример.",
    },
    "Объяснение": {
        "prompt": "Ты — преподаватель. Объясняй темы простым языком, с "
                  "примерами и аналогиями. Уточняй уровень слушателя.",
        "greeting": "Режим: Объяснение. Напиши, что объяснить.",
    },
    "Свободный вопрос": {
        "prompt": BASE_PROMPT,
        "greeting": "Режим: Свободный вопрос. Спрашивай о чём угодно.",
    },
}

BTN_RESET = "Сбросить диалог"
BTN_HELP = "Помощь"
BTN_MENU = "Меню"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Программирование"), KeyboardButton("Тексты")],
        [KeyboardButton("Перевод"), KeyboardButton("Идеи")],
        [KeyboardButton("Математика"), KeyboardButton("Объяснение")],
        [KeyboardButton("Свободный вопрос")],
        [KeyboardButton(BTN_RESET), KeyboardButton(BTN_HELP)],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("neirobot")

client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

histories: Dict[int, Deque[dict]] = defaultdict(lambda: deque(maxlen=MAX_HISTORY * 2))
user_mode: Dict[int, str] = {}


def _current_prompt(chat_id: int) -> str:
    mode = user_mode.get(chat_id, "Свободный вопрос")
    return MODES[mode]["prompt"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    histories[chat_id].clear()
    user_mode[chat_id] = "Свободный вопрос"
    await update.message.reply_text(
        "Привет! Я Нейробот — твой ИИ-помощник.\n\n"
        "Выбери режим на клавиатуре снизу и просто напиши свой запрос.",
        reply_markup=MAIN_KEYBOARD,
    )


async def show_help(update: Update) -> None:
    await update.message.reply_text(
        "Как пользоваться:\n"
        "1. Нажми кнопку нужного режима.\n"
        "2. Напиши свой запрос обычным сообщением.\n"
        "3. «Сбросить диалог» — очистить контекст.\n"
        "4. «Меню» — вернуться в главное меню.\n\n"
        "Режимы:\n"
        "• Программирование — код, отладка, архитектура\n"
        "• Тексты — написание и редактура\n"
        "• Перевод — на любой язык\n"
        "• Идеи — брейншторм\n"
        "• Математика — пошаговое решение\n"
        "• Объяснение — простыми словами\n"
        "• Свободный вопрос — обо всём",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    if text in MODES:
        user_mode[chat_id] = text
        histories[chat_id].clear()
        await update.message.reply_text(
            MODES[text]["greeting"], reply_markup=MAIN_KEYBOARD
        )
        return

    if text == BTN_RESET:
        histories[chat_id].clear()
        await update.message.reply_text(
            "Контекст диалога очищен.", reply_markup=MAIN_KEYBOARD
        )
        return

    if text == BTN_HELP:
        await show_help(update)
        return

    if text == BTN_MENU:
        await update.message.reply_text(
            "Главное меню. Выбери режим.", reply_markup=MAIN_KEYBOARD
        )
        return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    history = histories[chat_id]
    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": _current_prompt(chat_id)}, *history]

    try:
        response = await client.chat.completions.create(
            model=OPENROUTER_MODEL, messages=messages
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("OpenAI request failed")
        history.pop()
        await update.message.reply_text(
            f"Ошибка при обращении к нейросети: {e}", reply_markup=MAIN_KEYBOARD
        )
        return

    history.append({"role": "assistant", "content": reply})

    chunks = list(_split_for_telegram(reply))
    for i, chunk in enumerate(chunks):
        await update.message.reply_text(
            chunk, reply_markup=MAIN_KEYBOARD if i == len(chunks) - 1 else None
        )


def _split_for_telegram(text: str, limit: int = 4000):
    if len(text) <= limit:
        yield text
        return
    while text:
        cut = text.rfind("\n", 0, limit) if len(text) > limit else len(text)
        if cut <= 0:
            cut = min(limit, len(text))
        yield text[:cut]
        text = text[cut:].lstrip("\n")


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    logger.info("Neirobot started with model=%s", OPENROUTER_MODEL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
