# Neirobot

Telegram-бот через [OpenRouter](https://openrouter.ai/) — универсальный ИИ-помощник, отвечающий на любые вопросы и помогающий с любыми задачами (код, тексты, переводы, идеи, расчёты и т.д.). OpenRouter даёт доступ к десяткам моделей, в том числе **бесплатным** (Llama 3.3, DeepSeek, Gemini Flash и др.).

## Возможности

- Полностью кнопочный интерфейс — никаких команд кроме `/start`
- 7 режимов: Программирование, Тексты, Перевод, Идеи, Математика, Объяснение, Свободный вопрос
- В каждом режиме — свой system prompt, заточенный под задачу
- Контекст разговора (последние сообщения помнятся)
- Кнопка «Сбросить диалог» для очистки контекста
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
- `OPENROUTER_API_KEY` — ключ от [openrouter.ai/keys](https://openrouter.ai/keys)
- `OPENROUTER_MODEL` *(опционально)* — модель, по умолчанию `meta-llama/llama-3.3-70b-instruct:free`. Список моделей: [openrouter.ai/models](https://openrouter.ai/models) (модели с `:free` бесплатные)
- `MAX_HISTORY` *(опционально)* — сколько пар сообщений хранить в контексте, по умолчанию `20`

## Запуск

```bash
python bot.py
```

После запуска напишите боту в Telegram `/start`.

## Управление

| Кнопка / команда   | Действие                          |
|--------------------|-----------------------------------|
| `/start`           | Запуск бота, показ меню           |
| Режим (любой)      | Переключение в специальный режим  |
| `Сбросить диалог`  | Очистить историю                  |
| `Помощь`           | Справка                           |

## Структура

```
.
├── bot.py            # основной код бота
├── requirements.txt  # зависимости
├── .env.example      # пример переменных окружения
└── README.md
```
