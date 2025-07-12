import os
import re
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    filters
)

from db import (
    init_db, add_event, get_upcoming_events, delete_event,
    add_note, get_notes_by_tag, get_note_by_name, delete_note, rename_note
)
from scheduler import start_scheduler
from notio_bot.session_manager import switch_mode

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

init_db()
start_scheduler()
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()


# ========== ВСПОМОГАТЕЛЬНЫЕ ==========
def parse_date_time(date_str, time_str):
    try:
        now = datetime.now()
        dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m %H:%M")
        dt = dt.replace(year=now.year)
        return dt
    except ValueError:
        return None


# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    text_lower = text.lower()

    # Сохраняем ID входящего сообщения
    context.user_data.setdefault("messages_to_delete", []).append(update.message.message_id)

    # 1. Добавление события
    match = re.match(r"запомни (\d{2}\.\d{2}) в (\d{2}:\d{2}) (.+?)(?: напомни в (\d{2}:\d{2}))?$", text_lower)
    if match:
        date_str = match.group(1)
        time_str = match.group(2)
        event_name = match.group(3).strip()
        remind_time_str = match.group(4)

        event_datetime = parse_date_time(date_str, time_str)
        if not event_datetime:
            await update.message.reply_text("⚠️ Неверный формат даты или времени.")
            return

        remind_before = 3
        if remind_time_str:
            remind_time = parse_date_time(date_str, remind_time_str)
            if remind_time:
                remind_before = int((event_datetime - remind_time).total_seconds() / 3600)

        add_event(user_id, event_name, event_datetime, remind_before)
        await update.message.reply_text(f"✅ Запись '{event_name}' добавлена. Напомню за {remind_before} ч.")
        return

    # 2. Просмотр событий
    match = re.match(r"какие у меня планы на ближайшие(?: (\d+))?", text_lower)
    if match:
        days = int(match.group(1)) if match.group(1) else 7
        if days < 0:
            await update.message.reply_text("⚠️ Количество дней не может быть отрицательным.")
            return

        events = get_upcoming_events(user_id, days)
        if events:
            reply = f"📅 На ближайшие {days} дней:\n" + "\n".join(
                [f"{e['event_date'].strftime('%d.%m %H:%M')} {e['event_name']}" for e in events])
        else:
            reply = "📭 Нет запланированных событий."
        await update.message.reply_text(reply)
        return

    # 3. Удаление события
    match = re.match(r"отмени запись (.+)", text_lower)
    if match:
        event_name = match.group(1).strip()
        deleted = delete_event(user_id, event_name)
        if deleted:
            await update.message.reply_text(f"🗑️ Запись '{event_name}' удалена!")
        else:
            await update.message.reply_text("❗ Такой записи не существует.")
        return

    # 4. Создание заметки
    match = re.match(r"(создай|запиши) заметку[,:]?\s*(.+?):\s*(.+?)(?: с тегом (.+))?$", text_lower)
    if match:
        try:
            name = match.group(2).strip().capitalize()
            content = match.group(3).strip()
            tag = match.group(4).strip() if match.group(4) else ""
            add_note(user_id, name, content, [tag] if tag else [])
            reply = f"📝 Заметка '{name}'"
            if tag:
                reply += f" с тегом '{tag}'"
            reply += " успешно создана!"
            await update.message.reply_text(reply)
        except Exception as e:
            logging.error(f"[ADD_NOTE ERROR] {e}")
            await update.message.reply_text("⚠️ Не удалось сохранить заметку. Попробуйте позже.")
        return

    # 5. Просмотр заметок по тегу
    match = re.match(r"покажи список заметок с тегом (.+)", text_lower)
    if match:
        tag = match.group(1).strip()
        notes = get_notes_by_tag(user_id, tag)
        if notes:
            note_list = "\n".join([f"- {n['note_name']}" for n in notes])
            await update.message.reply_text(f"📚 Заметки с тегом '{tag}':\n{note_list}")
        else:
            await update.message.reply_text("📭 С указанным тегом пока нет заметок.")
        return

    # 6. Открыть заметку
    match = re.match(r"открой содержимое заметки (.+)", text_lower)
    if match:
        name = match.group(1).strip()
        note = get_note_by_name(user_id, name)
        if note:
            tag_part = f"\n#{note['tag']}" if note.get("tag") else ""
            await update.message.reply_text(f"{note['note_name']}\n{note['note_content']}{tag_part}")
        else:
            await update.message.reply_text(f"❗ Не найдено заметки с названием: {name}")
        return

    # 7. Удаление заметки
    match = re.match(r"удали заметку (.+)", text_lower)
    if match:
        name = match.group(1).strip()
        deleted = delete_note(user_id, name)
        if deleted:
            await update.message.reply_text(f"🗑️ Заметка '{name}' успешно удалена.")
        else:
            await update.message.reply_text("❗ Такой заметки не существует.")
        return

    # 8. Переименование заметки
    match = re.match(r"переименуй заметку (.+?) на (.+)", text_lower)
    if match:
        old_name = match.group(1).strip()
        new_name = match.group(2).strip()
        renamed = rename_note(user_id, old_name, new_name)
        if renamed:
            await update.message.reply_text(f"✏️ Заметка '{old_name}' переименована в '{new_name}'.")
        else:
            await update.message.reply_text("❗ Такой заметки не существует.")
        return

    await update.message.reply_text(
        "❗ Команда не распознана. Убедитесь, что вы используете точный шаблон.\n"
        "Например:\n`создай заметку ДЗ: выучить ИИ с тегом учеба`",
        parse_mode="Markdown"
    )


# ========== /START И КНОПКИ ==========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Календарь", callback_data='calendar')],
        [InlineKeyboardButton("📝 Заметки", callback_data='notes')],
        [InlineKeyboardButton("📘 Шаблоны", callback_data='templates')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Добро пожаловать!\nВыберите режим работы:",
        reply_markup=reply_markup
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # Очищаем предыдущие сообщения и переключаем режим
    await switch_mode_and_cleanup(query, context, query.data)

    if query.data == 'calendar':
        await query.message.reply_text(
            "📅 *Календарь:*\n"
            "`запомни 13.07 в 14:00 встреча с другом напомни в 12:00`\n"
            "`какие у меня планы на ближайшие 7`\n"
            "`отмени запись встреча с другом`",
            parse_mode="Markdown"
        )
    elif query.data == 'notes':
        await query.message.reply_text(
            "📝 *Заметки:*\n"
            "`создай заметку ДЗ: выучить ИИ с тегом учеба`\n"
            "`запиши заметку Дом: убраться дома`\n"
            "`покажи список заметок с тегом учеба`\n"
            "`открой содержимое заметки ДЗ`\n"
            "`удали заметку Дом`\n"
            "`переименуй заметку ДЗ на Домашка`",
            parse_mode="Markdown"
        )
    elif query.data == 'templates':
        await query.message.reply_text(
            "📘 *Все шаблоны (обязательно соблюдать формат):*\n\n"
            "🗓 `запомни <дата> в <время> <действие> напомни в <время>`\n"
            "🗓 `какие у меня планы на ближайшие <число>`\n"
            "🗓 `отмени запись <название>`\n"
            "📝 `создай/запиши заметку Название: текст с тегом Тег`\n"
            "📝 `открой содержимое заметки Название`\n"
            "📝 `удали заметку Название`\n"
            "📝 `переименуй заметку Старое на Новое`",
            parse_mode="Markdown"
        )


# ========== РЕГИСТРАЦИЯ ==========
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
