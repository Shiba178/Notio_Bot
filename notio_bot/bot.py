import os
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from db import (
    init_db, add_event, get_upcoming_events, delete_event,
    add_note, get_notes_by_tag, get_note_by_name, delete_note, rename_note
)
from scheduler import start_scheduler
from parsing import parse_message

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Инициализация базы и планировщика
init_db()
start_scheduler()

# Создание приложения
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Основная клавиатура
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        ["Добавить заметку", "Показать заметки"],
        ["Добавить событие", "Показать планы"],
        ["Помощь"]
    ],
    resize_keyboard=True
)

# /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я — твой ассистент по заметкам и напоминаниям.\n\n"
        "📌 Используйте команды строго по шаблонам (см. /help).\n"
        "✅ Готов к работе!",
        reply_markup=main_keyboard
    )

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 <b>Шаблоны команд:</b>\n\n"
        "🗓 <b>Календарь:</b>\n"
        "• запомни 13.07 в 12:00 стоматолог напомни в 10:00\n"
        "• какие у меня планы на ближайшие 3 дня\n"
        "• отмени запись стоматолог\n\n"
        "📝 <b>Заметки:</b>\n"
        "• создай заметку Дом: убрать дома с тегом дела\n"
        "• запиши заметку ДЗ: повторить тему\n"
        "• открой содержимое заметки ДЗ\n"
        "• покажи список заметок с тегом учеба\n"
        "• удали заметку ДЗ\n"
        "• переименуй заметку ДЗ на Домашка\n\n"
        "⌨️ Используйте <b>точные формулировки</b>, иначе бот не поймёт.",
        parse_mode="HTML"
    )

# /restart
async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)

# Обработка текстовых команд
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text.strip()

    try:
        result = parse_message(user_message)
    except Exception as e:
        logging.error(f"[PARSING ERROR] {e}")
        await update.message.reply_text("⚠️ Я не смог разобрать ваш запрос. Убедитесь в правильности шаблона.")
        return

    action = result.get("action")
    details = result.get("details")

    try:
        if action == "create_event":
            name = details["name"]
            date = details["date"]
            remind = details["remind"]
            add_event(user_id, name, date, remind)
            await update.message.reply_text(
                f"🗓 Запись «{name}» успешно добавлена на {date.strftime('%d.%m %H:%M')}! Напомню за {remind} ч."
            )

        elif action == "list_events":
            days = details["days"]
            events = get_upcoming_events(user_id, days)
            if events:
                msg = f"📅 Ваши планы на ближайшие {days} дней:\n" + "\n".join(
                    [f"{e['event_date'].strftime('%d.%m %H:%M')} — {e['event_name']}" for e in events]
                )
            else:
                msg = "📭 У вас пока нет запланированных событий."
            await update.message.reply_text(msg)

        elif action == "delete_event":
            name = details["name"]
            deleted = delete_event(user_id, name)
            if deleted:
                await update.message.reply_text(f"🗑 Запись «{name}» удалена!")
            else:
                await update.message.reply_text("❌ Такой записи нет. Посмотрите список ваших событий.")

        elif action == "create_note":
            name = details["name"]
            content = details["content"]
            tags = details.get("tags", [])
            add_note(user_id, name, content, tags)
            tag_msg = f" и тегом #{tags[0]}" if tags else ""
            await update.message.reply_text(f"📝 Заметка «{name}»{tag_msg} успешно создана!")

        elif action == "list_notes":
            tag = details["tag"]
            notes = get_notes_by_tag(user_id, tag)
            if notes:
                msg = f"📚 Заметки с тегом #{tag}:\n" + "\n".join([f"— {n['note_name']}" for n in notes])
            else:
                msg = "📭 С заметками с этим тегом ничего не найдено."
            await update.message.reply_text(msg)

        elif action == "open_note":
            name = details["name"]
            note = get_note_by_name(user_id, name)
            if note:
                content = f"📖 {note['note_name']}\n{note['note_content']}"
                if note['tags']:
                    content += f"\n#{note['tags'][0]}"
                await update.message.reply_text(content)
            else:
                await update.message.reply_text(f"❌ Не могу найти заметку «{name}».")

        elif action == "delete_note":
            name = details["name"]
            deleted = delete_note(user_id, name)
            if deleted:
                await update.message.reply_text(f"🗑 Заметка «{name}» удалена.")
            else:
                await update.message.reply_text("❌ Такой заметки не существует.")

        elif action == "rename_note":
            old_name = details["old_name"]
            new_name = details["new_name"]
            renamed = rename_note(user_id, old_name, new_name)
            if renamed:
                await update.message.reply_text(f"✏️ Заметка «{old_name}» переименована в «{new_name}».")
            else:
                await update.message.reply_text("❌ Не удалось найти или переименовать заметку.")

        else:
            await update.message.reply_text("🤖 Команда не распознана. Используйте /help для подсказок.")
    except Exception as e:
        logging.error(f"[HANDLER ERROR] {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при обработке запроса. Попробуйте снова.")

# ==================== Обработчики ====================
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("restart", restart_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ==================== Запуск ====================
app.run_polling()