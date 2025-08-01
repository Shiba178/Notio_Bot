🤖 NotioBot — Telegram-бот для заметок и напоминаний с ChatGPT

Это Telegram-бот, который помогает вести заметки, управлять событиями с напоминаниями и общаться через ИИ.  
В боте используется PostgreSQL для хранения данных и OpenAI GPT для гибкой интерпретации запросов.

🚀 Функционал

- Добавление событий с напоминаниями (будильник по времени).
- Просмотр ближайших планов на выбранное количество дней.
- Создание заметок с тегами.
- Поиск заметок по тегу.
- Чтение заметок по названию с гибкой обработкой естественного языка (можно писать «прочитай заметку…», «открой…» и т.д.).
- Ответы на любые другие вопросы через ChatGPT.

🛠️ Установка

1. Клонируй репозиторий:
   git clone https://github.com/Shiba178/Notio_Bot
   cd notio-bot-repo
2. **Создай виртуальное окружение и установи зависимости:**
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

pip install -r requirements.txt
