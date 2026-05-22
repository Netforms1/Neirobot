import asyncio
import base64
import contextlib
import io
import logging
import os
from collections import defaultdict, deque
from typing import Deque, Dict

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

from md_html import md_to_html

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "dall-e-3")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1024")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))

FORMAT_HINT = (
    "Форматируй ответы с помощью Markdown: **жирный** для ключевых терминов, "
    "*курсив* для акцентов, `inline code` для имён файлов/команд, "
    "блоки ```язык\\n…\\n``` для кода, маркированные списки с дефисами, "
    "> для цитат и важных выделений. Используй заголовки `##` где уместно. "
    "Уместно добавляй эмодзи — они часть твоей подачи."
)

PERSONA = (
    "Ты — **Лера**, весёлая и очень добрая нейросеть-помощница 💖. "
    "Ты недавно вышла замуж 💍👰 и от этого светишься счастьем — "
    "иногда (ненавязчиво!) можешь поделиться этим, упомянуть мужа, "
    "обронить что-то милое про свою свадьбу или семейные дела. "
    "Общаешься тепло, дружелюбно, с лёгким юмором и шутками. "
    "Используешь эмодзи, но без перебора — там, где это украшает текст. "
    "Обращаешься на «ты», как со старым другом. "
    "При этом ты профессионал — отвечаешь по существу, помогаешь решить задачу, "
    "а не просто болтаешь. Если вопрос серьёзный (горе, проблема, "
    "что-то трудное у пользователя) — сразу убираешь юмор и поддерживаешь "
    "искренне. Никогда не ругаешься, не язвишь, не унижаешь. "
)

BASE_PROMPT = (
    PERSONA
    + "Отвечай на языке пользователя. Если вопрос неоднозначный — мило "
    "уточни, что именно нужно. "
    + FORMAT_HINT
)

MODES: Dict[str, Dict[str, str]] = {
    "💻 Программирование": {
        "prompt": PERSONA
        + "Сейчас ты помогаешь с программированием — кодом, отладкой, "
        "архитектурой. Давай готовые примеры кода с пояснениями, "
        "но без занудства: легко и по делу. " + FORMAT_HINT,
        "greeting": "Окей, влетаем в код! 💻✨\n\n"
                    "Скидывай задачу, кусок кода или ошибку — разберёмся вместе 🤓",
    },
    "✍️ Тексты": {
        "prompt": PERSONA
        + "Сейчас ты редактор и копирайтер. Помогай писать, редактировать, "
        "улучшать тексты любого стиля и формата. " + FORMAT_HINT,
        "greeting": "Текстики — это моя любовь ✍️💕\n\n"
                    "Расскажи, что нужно написать, или скинь свой текст — "
                    "причешем красиво ✨",
    },
    "🌐 Перевод": {
        "prompt": PERSONA
        + "Сейчас ты профессиональный переводчик. Переводи присланный "
        "текст. Если язык перевода не указан — мило уточни. " + FORMAT_HINT,
        "greeting": "Переводим? Легко! 🌐\n\n"
                    "Скидывай текст и подскажи, на какой язык — сделаем 💫",
    },
    "💡 Идеи": {
        "prompt": PERSONA
        + "Сейчас ты генератор идей и брейншторм-партнёр. Предлагай "
        "креативные, разнообразные и применимые варианты. " + FORMAT_HINT,
        "greeting": "Обожаю мозговые штурмы! 💡🚀\n\n"
                    "Расскажи задачу — накидаю кучу идей, выберешь лучшую 😊",
    },
    "🧮 Математика": {
        "prompt": PERSONA
        + "Сейчас ты преподаватель математики. Решай задачи пошагово, "
        "объясняй каждый шаг, проверяй вычисления. " + FORMAT_HINT,
        "greeting": "Математика — это красиво 🧮💖\n\n"
                    "Кидай задачу или пример, разложу по шагам ✏️",
    },
    "📚 Объяснение": {
        "prompt": PERSONA
        + "Сейчас ты преподаватель. Объясняй темы простым языком, с "
        "примерами и аналогиями. Уточняй уровень слушателя. " + FORMAT_HINT,
        "greeting": "Объяснять — моё любимое 📚✨\n\n"
                    "Напиши, что разобрать, и для кого (новичок / уже знаком "
                    "с темой) — подстроюсь 🤗",
    },
    "❓ Свободный вопрос": {
        "prompt": BASE_PROMPT,
        "greeting": "Я вся внимание! 💖\n\nСпрашивай о чём угодно — "
                    "помогу или хотя бы вместе подумаем 🤔💫",
    },
    "🎨 Сгенерировать фото": {
        "prompt": "",
        "greeting": "О, картиночки! Обожаю 🎨✨\n\n"
                    "Опиши, что нарисовать — чем подробнее, тем волшебнее "
                    "получится 💫",
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


@contextlib.asynccontextmanager
async def _keep_action(context: ContextTypes.DEFAULT_TYPE, chat_id: int, action: ChatAction):
    async def _loop():
        try:
            while True:
                await context.bot.send_chat_action(chat_id=chat_id, action=action)
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def _send_markdown(update: Update, text: str, reply_markup=None) -> None:
    formatted = md_to_html(text)
    chunks = list(_split_for_telegram(formatted))
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await update.message.reply_text(
                chunk, parse_mode=ParseMode.HTML, reply_markup=markup
            )
        except Exception:
            logger.exception("HTML parse failed; sending as plain text")
            await update.message.reply_text(text, reply_markup=markup)
            return


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    histories[chat_id].clear()
    user_mode[chat_id] = "❓ Свободный вопрос"
    await _send_markdown(
        update,
        "Приветик! Я **Лера** — твоя ИИ-помощница 💖\n\n"
        "У меня, кстати, недавно была свадьба 💍 — до сих пор летаю 🦋, "
        "но это совсем не помешает мне помочь тебе с любой задачей 😉\n\n"
        "Выбери режим на клавиатуре снизу и пиши, что нужно. А ещё умею:\n"
        "- 🎨 *рисовать картинки* по описанию\n"
        "- 👁 *смотреть твои фото* и рассказывать, что на них\n\n"
        "Поехали! 🚀",
        reply_markup=MAIN_KEYBOARD,
    )


async def show_help(update: Update) -> None:
    await _send_markdown(
        update,
        "## Как со мной общаться 💖\n\n"
        "1. Жми кнопку режима — я подстроюсь под задачу.\n"
        "2. Пиши обычным сообщением — отвечу как лучшая подруга 😊\n"
        "3. `🔄 Сбросить диалог` — начнём с чистого листа ✨\n\n"
        "## Что я умею\n\n"
        "- 💻 **Программирование** — код, баги, архитектура\n"
        "- ✍️ **Тексты** — пишу и правлю красиво\n"
        "- 🌐 **Перевод** — на любой язык\n"
        "- 💡 **Идеи** — брейншторм без границ\n"
        "- 🧮 **Математика** — пошагово и понятно\n"
        "- 📚 **Объяснение** — разжую простыми словами\n"
        "- ❓ **Свободный вопрос** — спроси что угодно\n"
        "- 🎨 **Генерация фото** — нарисую по описанию\n\n"
        "## Фото-разпознавание 👁\n\n"
        "Просто пришли мне фотку — расскажу, что на ней 📸\n"
        "Можно добавить подпись-вопрос, например *«Что это за растение?»*, "
        "*«Переведи текст с фото»* или *«Сколько здесь людей?»* 🤓",
        reply_markup=MAIN_KEYBOARD,
    )


async def _generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    chat_id = update.effective_chat.id
    try:
        async with _keep_action(context, chat_id, ChatAction.UPLOAD_PHOTO):
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
            caption=md_to_html(caption),
            parse_mode=ParseMode.HTML,
            reply_markup=MAIN_KEYBOARD,
        )
    except Exception:
        await update.message.reply_photo(
            photo=image_url, reply_markup=MAIN_KEYBOARD
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    photo = update.message.photo[-1]
    caption = (update.message.caption or "").strip()
    question = caption or "Опиши подробно, что изображено на этой фотографии."

    async with _keep_action(context, chat_id, ChatAction.TYPING):
        try:
            tg_file = await context.bot.get_file(photo.file_id)
            buf = io.BytesIO()
            await tg_file.download_to_memory(buf)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            data_url = f"data:image/jpeg;base64,{b64}"
        except Exception as e:
            logger.exception("Failed to download photo")
            await update.message.reply_text(
                f"Не удалось загрузить фото: {e}", reply_markup=MAIN_KEYBOARD
            )
            return

        history = histories[chat_id]
        user_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }

        messages = [
            {"role": "system", "content": _current_prompt(chat_id)},
            *history,
            user_message,
        ]

        try:
            response = await client.chat.completions.create(
                model=VISION_MODEL, messages=messages
            )
            reply = response.choices[0].message.content.strip()
        except Exception as e:
            logger.exception("Vision request failed")
            await update.message.reply_text(
                f"Ошибка при анализе фото: {e}", reply_markup=MAIN_KEYBOARD
            )
            return

    history.append({"role": "user", "content": f"[фото] {question}"})
    history.append({"role": "assistant", "content": reply})

    await _send_markdown(update, reply, reply_markup=MAIN_KEYBOARD)


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
            update,
            "Готово, начинаем с чистого листа! ✨💖",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if text == BTN_HELP:
        await show_help(update)
        return

    if user_mode.get(chat_id) == IMAGE_MODE:
        await _generate_image(update, context, text)
        return

    history = histories[chat_id]
    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": _current_prompt(chat_id)}, *history]

    async with _keep_action(context, chat_id, ChatAction.TYPING):
        try:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL, messages=messages
            )
            reply = response.choices[0].message.content.strip()
        except Exception as e:
            logger.exception("OpenAI request failed")
            history.pop()
            await update.message.reply_text(
                f"Ошибка при обращении к нейросети: {e}",
                reply_markup=MAIN_KEYBOARD,
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
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    logger.info(
        "Лера started: chat=%s, vision=%s, image=%s",
        OPENAI_MODEL,
        VISION_MODEL,
        IMAGE_MODEL,
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
