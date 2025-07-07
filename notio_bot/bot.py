import os
import json
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI
from db import init_db, add_event, get_upcoming_events, add_note, get_notes_by_tag, get_note_by_name
from scheduler import start_scheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_KEY:
    logger.error("Не заданы TELEGRAM_TOKEN или OPENAI_API_KEY в переменных окружения!")
    raise ValueError("Требуются TELEGRAM_TOKEN и OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

# Инициализация базы данных и планировщика
try:
    init_db()
    start_scheduler()
except Exception as e:
    logger.error(f"Ошибка инициализации БД или планировщика: {e}")
    raise

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    user_message = update.message.text.strip()
    logger.info(f"[USER {user_id}] {user_message}")

    try:
        # Запрос к OpenAI
        gpt_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты ассистент для Telegram-бота с функциями календаря и заметок. "
                        "На основе запроса пользователя определи одно из действий: "
                        "1) создать_событие, 2) показать_события, 3) создать_заметку, "
                        "4) показать_заметки_по_тегу, 5) открыть_заметку, 6) другое. "
                        "Ответь строго в формате JSON с ключами: action и details."
                    )
                },
                {"role": "user", "content": user_message}
            ],
            temperature=0.3  # Для более предсказуемых ответов
        )

        response_content = gpt_response.choices[0].message.content
        parsed = json.loads(response_content)
        action = parsed.get("action")
        details = parsed.get("details", {})

        logger.info(f"Parsed response: action={action}, details={details}")

    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON от OpenAI: {e}")
        await update.message.reply_text("❗ Не удалось обработать ответ сервера. Попробуйте позже.")
        return
    except Exception as e:
        logger.error(f"Ошибка запроса к OpenAI: {e}")
        await update.message.reply_text("❗ Ошибка связи с сервером ИИ. Попробуйте позже.")
        return

    try:
        if action == "создать_событие":
            required_fields = ["название", "дата"]
            if not all(field in details for field in required_fields):
                raise ValueError("Отсутствуют обязательные поля")

            event_name = details["название"]
            date_str = details["дата"]
            remind_before = int(details.get("напоминание_за", 24))
            
            try:
                event_date = datetime.strptime(date_str, "%d.%m.%y %H:%M")
            except ValueError:
                event_date = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
            
            add_event(user_id, event_name, event_date, remind_before)
            await update.message.reply_text(
                f"✅ Событие '{event_name}' создано на {event_date.strftime('%d.%m.%Y %H:%M')} "
                f"с напоминанием за {remind_before} ч."
            )

        elif action == "показать_события":
            days = int(details.get("дней", 7))
            events = get_upcoming_events(user_id, days)
            
            if events:
                msg = "📅 Ваши планы:\n" + "\n".join(
                    [f"— {e['event_name']} — {e['event_date'].strftime('%d.%m.%Y %H:%M')}" 
                     for e in events]
                )
            else:
                msg = "📭 Нет запланированных событий."
            await update.message.reply_text(msg)

        elif action == "создать_заметку":
            required_fields = ["название", "содержание"]
            if not all(field in details for field in required_fields):
                raise ValueError("Отсутствуют обязательные поля")

            name = details["название"]
            content = details["содержание"]
            tags = details.get("теги", [])
            
            if isinstance(tags, str):
                tags = [tag.strip() for tag in tags.split(",")]
            
            add_note(user_id, name, content, tags)
            await update.message.reply_text(f"📝 Заметка '{name}' создана.")

        elif action == "показать_заметки_по_тегу":
            if "тег" not in details:
                raise ValueError("Не указан тег")
                
            tag = details["тег"]
            notes = get_notes_by_tag(user_id, tag)
            
            if notes:
                msg = "📚 Заметки:\n" + "\n".join([f"- {n['note_name']}" for n in notes])
            else:
                msg = "📭 Заметок с таким тегом нет."
            await update.message.reply_text(msg)

        elif action == "открыть_заметку":
            if "название" not in details:
                raise ValueError("Не указано название заметки")
                
            name = details["название"]
            note = get_note_by_name(user_id, name)
            
            if note:
                await update.message.reply_text(f"📖 {note['note_name']}:\n{note['note_content']}")
            else:
                await update.message.reply_text("📭 Заметка не найдена.")

        else:
            await update.message.reply_text("🤖 Не уверен, как помочь с этим. Попробуйте переформулировать.")

    except KeyError as e:
        logger.error(f"Отсутствует обязательное поле: {e}")
        await update.message.reply_text("❗ В запросе отсутствуют необходимые данные.")
    except ValueError as e:
        logger.error(f"Некорректные данные: {e}")
        await update.message.reply_text(f"❗ Некорректные данные: {e}")
    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}")
        await update.message.reply_text("❗ Произошла внутренняя ошибка. Попробуйте позже.")

# Регистрация обработчиков
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

async def post_init(application):
    await application.bot.set_my_commands([
        ("start", "Начало работы"),
        ("help", "Помощь")
    ])

app.post_init(post_init)

if __name__ == "__main__":
    app.run_polling()
