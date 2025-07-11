import os
import json
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI
from db import init_db, add_event, get_upcoming_events, add_note, get_notes_by_tag, get_note_by_name
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)

# Инициализация базы данных и планировщика
init_db()
start_scheduler()

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text.strip()
    logging.info(f"[USER {user_id}] {user_message}")

    try:
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
            ]
        )

        parsed = json.loads(gpt_response.choices[0].message.content)
        action = parsed.get("action")
        details = parsed.get("details", {})

    except Exception as e:
        logging.error(f"Ошибка парсинга ответа ИИ: {e}")
        await update.message.reply_text("❗ Я не понял ваш запрос, попробуйте иначе.")
        return

    try:
        if action == "создать_событие":
            event_name = details["название"]
            date_str = details["дата"]
            remind_before = int(details.get("напоминание_за", 24))
            event_date = datetime.strptime(date_str, "%d.%m.%y %H:%M")
            add_event(user_id, event_name, event_date, remind_before)
            await update.message.reply_text(
                f"✅ Событие '{event_name}' создано на {event_date} с напоминанием за {remind_before} ч."
            )

        elif action == "показать_события":
            days = int(details.get("дней", 7))
            events = get_upcoming_events(user_id, days)
            if events:
                msg = "📅 Ваши планы:\n" + "\n".join(
                    [f"— {e['event_name']} — {e['event_date']}" for e in events]
                )
            else:
                msg = "📭 Нет запланированных событий."
            await update.message.reply_text(msg)

        elif action == "создать_заметку":
            name = details["название"]
            content = details["содержание"]
            tags = details.get("теги", [])
            add_note(user_id, name, content, tags)
            await update.message.reply_text(f"📝 Заметка '{name}' создана.")

        elif action == "показать_заметки_по_тегу":
            tag = details["тег"]
            notes = get_notes_by_tag(user_id, tag)
            if notes:
                msg = "📚 Заметки:\n" + "\n".join([f"- {n['note_name']}" for n in notes])
            else:
                msg = "📭 Заметок с таким тегом нет."
            await update.message.reply_text(msg)

        elif action == "открыть_заметку":
            name = details["название"]
            note = get_note_by_name(user_id, name)
            if note:
                await update.message.reply_text(f"📖 {note['note_name']}:\n{note['note_content']}")
            else:
                await update.message.reply_text("📭 Заметка не найдена.")

        else:
            await update.message.reply_text("🤖 Не уверен, как помочь с этим. Попробуйте переформулировать.")
            except Exception as e:
        logging.error(f"Ошибка при выполнении действия: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при выполнении запроса.")

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
