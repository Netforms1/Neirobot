import asyncio
import logging
import os
from collections import defaultdict, deque
from typing import Deque, Dict

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
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
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))

SYSTEM_PROMPT = (
    "Ты — Нейробот, полезный универсальный ИИ-ассистент. "
    "Помогаешь пользователю с любыми задачами: программирование, тексты, "
    "переводы, объяснения, идеи, расчёты, советы. "
    "Отвечай чётко, по делу и на том языке, на котором обращается пользователь. "
    "Если вопрос неоднозначный — задай уточняющий вопрос."
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("neirobot")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

histories: Dict[int, Deque[dict]] = defaultdict(lambda: deque(maxlen=MAX_HISTORY * 2))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    histories[update.effective_chat.id].clear()
    await update.message.reply_text(
        "Привет! Я Нейробот — твой ИИ-помощник на базе GPT.\n\n"
        "Просто напиши мне любой вопрос или задачу.\n\n"
        "Команды:\n"
        "/reset — очистить историю диалога\n"
        "/help — справка"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Я могу:\n"
        "• Отвечать на вопросы\n"
        "• Писать и объяснять код\n"
        "• Переводить и редактировать тексты\n"
        "• Помогать с идеями и планированием\n"
        "• Делать расчёты и анализ\n\n"
        "/reset — сбросить контекст разговора"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    histories[update.effective_chat.id].clear()
    await update.message.reply_text("Контекст диалога очищен.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_text = update.message.text

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    history = histories[chat_id]
    history.append({"role": "user", "content": user_text})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]

    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("OpenAI request failed")
        history.pop()
        await update.message.reply_text(f"Ошибка при обращении к нейросети: {e}")
        return

    history.append({"role": "assistant", "content": reply})

    for chunk in _split_for_telegram(reply):
        await update.message.reply_text(chunk)


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
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Neirobot started with model=%s", OPENAI_MODEL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
