# Neirobot

Telegram-бот на базе OpenAI GPT — универсальный ИИ-помощник, отвечающий на любые вопросы и помогающий с любыми задачами (код, тексты, переводы, идеи, расчёты и т.д.).

## Возможности

- Диалог с GPT прямо в Telegram
- Контекст разговора (последние сообщения помнятся)
- Команды `/start`, `/help`, `/reset`
- Автоматическое разбиение длинных ответов под лимит Telegram (4096 символов)
- Индикатор «печатает...» во время генерации

## Установка

```bash
git clone https://github.com/netforms1/neirobot.git
cd neirobot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Настройка

В файле `.env` укажите:

- `TELEGRAM_TOKEN` — токен бота от [@BotFather](https://t.me/BotFather)
- `OPENAI_API_KEY` — ключ от [platform.openai.com](https://platform.openai.com/)
- `OPENAI_MODEL` *(опционально)* — модель, по умолчанию `gpt-4o-mini`
- `MAX_HISTORY` *(опционально)* — сколько пар сообщений хранить в контексте, по умолчанию `20`

## Запуск

```bash
python bot.py
```

После запуска напишите боту в Telegram `/start`.

## Команды

| Команда  | Описание                          |
|----------|-----------------------------------|
| `/start` | Приветствие и сброс контекста     |
| `/help`  | Список возможностей               |
| `/reset` | Очистить историю диалога          |

## Структура

```
.
├── bot.py            # основной код бота
├── requirements.txt  # зависимости
├── .env.example      # пример переменных окружения
└── README.md
```
