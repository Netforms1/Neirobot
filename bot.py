import logging
import os
from collections import defaultdict, deque
from typing import Deque, Dict

import telegramify_markdown
from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "dall-e-3")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1024")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))

FORMAT_HINT = (
    "Форматируй ответы с помощью Markdown: **жирный** для ключевых терминов, "
    "*курсив* для акцентов, `inline code` для имён файлов/команд, "
    "блоки ```язык\\n…\\n``` для кода, маркированные списки с дефисами, "
    "> для цитат и важных выделений. Используй заголовки `##` где уместно."
)

BASE_PROMPT = (
    "Ты — Нейробот, универсальный ИИ-помощник. Отвечай чётко, по делу, "
    "на языке пользователя. Если вопрос неоднозначный — задай уточняющий вопрос. "
    + FORMAT_HINT
)

MODES: Dict[str, Dict[str, str]] = {
    "💻 Программирование": {
        "prompt": "Ты — опытный программист. Помогай с кодом, отладкой, "
                  "архитектурой. Давай готовые примеры кода с пояснениями. "
                  + FORMAT_HINT,
        "greeting": "Режим: *Программирование* 💻\n\nОпиши задачу, вставь код "
                    "или ошибку — помогу разобраться.",
    },
    "✍️ Тексты": {
        "prompt": "Ты — редактор и копирайтер. Помогай писать, редактировать, "
                  "улучшать тексты любого стиля и формата. " + FORMAT_HINT,
        "greeting": "Режим: *Тексты* ✍️\n\nНапиши, какой текст нужен (или "
                    "вставь существующий для правки).",
    },
    "🌐 Перевод": {
        "prompt": "Ты — профессиональный переводчик. Переводи присланный "
                  "текст. Если язык перевода не указан — спрашивай. "
                  + FORMAT_HINT,
        "greeting": "Режим: *Перевод* 🌐\n\nПришли текст и укажи язык, на "
                    "который перевести.",
    },
    "💡 Идеи": {
        "prompt": "Ты — генератор идей и брейншторм-партнёр. Предлагай "
                  "креативные, разнообразные и применимые варианты. "
                  + FORMAT_HINT,
        "greeting": "Режим: *Идеи* 💡\n\nОпиши задачу — накидаю варианты.",
    },
    "🧮 Математика": {
        "prompt": "Ты — преподаватель математики. Решай задачи пошагово, "
                  "объясняй каждый шаг, проверяй вычисления. " + FORMAT_HINT,
        "greeting": "Режим: *Математика* 🧮\n\nПришли задачу или пример.",
    },
    "📚 Объяснение": {
        "prompt": "Ты — преподаватель. Объясняй темы простым языком, с "
                  "примерами и аналогиями. Уточняй уровень слушателя. "
                  + FORMAT_HINT,
        "greeting": "Режим: *Объяснение* 📚\n\nНапиши, что объяснить.",
    },
    "❓ Свободный вопрос": {
        "prompt": BASE_PROMPT,
        "greeting": "Режим: *Свободный вопрос* ❓\n\nСпрашивай о чём угодно.",
    },
    "🎨 Сгенерировать фото": {
        "prompt": "",
        "greeting": "Режим: *Генерация фото* 🎨\n\nОпиши, что нарисовать — "
                    "и я сгенерирую изображение. Чем подробнее описание, тем "
                    "точнее результат.",
        "image": True,
    },
}

IMAGE_MODE = "🎨 Сгенерировать фото"
BTN_RESET = "🔄 Сбросить диалог"
BTN_HELP = "ℹ️ Помощь"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("💻 Программирование"), KeyboardButton("✍️ Тексты")],
        [KeyboardButton("🌐 Перевод"), KeyboardButton("💡 Идеи")],
        [KeyboardButton("🧮 Математика"), KeyboardButton("📚 Объяснение")],
        [KeyboardButton("❓ Свободный вопрос")],
        [KeyboardButton(IMAGE_MODE)],
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

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

histories: Dict[int, Deque[dict]] = defaultdict(lambda: deque(maxlen=MAX_HISTORY * 2))
user_mode: Dict[int, str] = {}


def _current_prompt(chat_id: int) -> str:
    mode = user_mode.get(chat_id, "❓ Свободный вопрос")
    return MODES[mode]["prompt"] or BASE_PROMPT


async def _send_markdown(update: Update, text: str, reply_markup=None) -> None:
    formatted = telegramify_markdown.markdownify(text)
    for chunk in _split_for_telegram(formatted):
        try:
            await update.message.reply_text(
                chunk,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup,
            )
        except Exception:
            await update.message.reply_text(chunk, reply_markup=reply_markup)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    histories[chat_id].clear()
    user_mode[chat_id] = "❓ Свободный вопрос"
    await _send_markdown(
        update,
        "Привет! Я **Нейробот** — твой ИИ-помощник 🤖\n\n"
        "Выбери режим на клавиатуре снизу и просто напиши свой запрос.\n\n"
        "Доступна также *генерация фото* по описанию 🎨",
        reply_markup=MAIN_KEYBOARD,
    )


async def show_help(update: Update) -> None:
    await _send_markdown(
        update,
        "## Как пользоваться\n\n"
        "1. Нажми кнопку нужного режима.\n"
        "2. Напиши свой запрос обычным сообщением.\n"
        "3. `🔄 Сбросить диалог` — очистить контекст.\n\n"
        "## Режимы\n\n"
        "- 💻 **Программирование** — код, отладка, архитектура\n"
        "- ✍️ **Тексты** — написание и редактура\n"
        "- 🌐 **Перевод** — на любой язык\n"
        "- 💡 **Идеи** — брейншторм\n"
        "- 🧮 **Математика** — пошаговое решение\n"
        "- 📚 **Объяснение** — простыми словами\n"
        "- ❓ **Свободный вопрос** — обо всём\n"
        "- 🎨 **Генерация фото** — изображение по описанию",
        reply_markup=MAIN_KEYBOARD,
    )


async def _generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
    try:
        response = await client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            size=IMAGE_SIZE,
            n=1,
        )
        image_url = response.data[0].url
        revised = getattr(response.data[0], "revised_prompt", None)
        caption = f"🎨 _{prompt}_" if not revised else f"🎨 _{revised[:900]}_"
    except Exception as e:
        logger.exception("Image generation failed")
        await update.message.reply_text(
            f"Не удалось сгенерировать изображение: {e}",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    try:
        await update.message.reply_photo(
            photo=image_url,
            caption=telegramify_markdown.markdownify(caption),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=MAIN_KEYBOARD,
        )
    except Exception:
        await update.message.reply_photo(
            photo=image_url, reply_markup=MAIN_KEYBOARD
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    if text in MODES:
        user_mode[chat_id] = text
        histories[chat_id].clear()
        await _send_markdown(update, MODES[text]["greeting"], reply_markup=MAIN_KEYBOARD)
        return

    if text == BTN_RESET:
        histories[chat_id].clear()
        await _send_markdown(
            update, "✅ Контекст диалога очищен.", reply_markup=MAIN_KEYBOARD
        )
        return

    if text == BTN_HELP:
        await show_help(update)
        return

    if user_mode.get(chat_id) == IMAGE_MODE:
        await _generate_image(update, context, text)
        return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    history = histories[chat_id]
    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": _current_prompt(chat_id)}, *history]

    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL, messages=messages
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
    await _send_markdown(update, reply, reply_markup=MAIN_KEYBOARD)


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
    logger.info(
        "Neirobot started: chat=%s, image=%s", OPENAI_MODEL, IMAGE_MODEL
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
