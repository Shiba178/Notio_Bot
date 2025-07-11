import os
import re
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from db import init_db, add_event, get_upcoming_events, delete_event, add_note, get_notes_by_tag, get_note_by_name, delete_note, rename_note
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Инициализация
init_db()
start_scheduler()

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# =============================== ПАРСЕР ===============================
def parse_date_time(date_str, time_str):
    try:
        now = datetime.now()
        dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m %H:%M")
        dt = dt.replace(year=now.year)
        return dt
    except ValueError:
        return None

# =============================== ОБРАБОТЧИК ===============================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    text_lower = text.lower()

    # ========== 1. ДОБАВЛЕНИЕ ЗАПИСИ В КАЛЕНДАРЬ ==========
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

        if remind_time_str:
            remind_time = parse_date_time(date_str, remind_time_str)
            if remind_time:
                remind_before = int((event_datetime - remind_time).total_seconds() / 3600)
            else:
                remind_before = 3
        else:
            remind_before = 3

        add_event(user_id, event_name, event_datetime, remind_before)
        await update.message.reply_text(f"✅ Запись в календаре '{event_name}' успешно добавлена. Напомню за {remind_before} ч.")
        return

    # ========== 2. ПРОСМОТР ЗАПИСЕЙ ==========
    match = re.match(r"какие у меня планы на ближайшие(?: (\d+))?", text_lower)
    if match:
        days = int(match.group(1)) if match.group(1) else 7
        if days < 0:
            await update.message.reply_text("⚠️ Количество дней не может быть отрицательным.")
            return

        events = get_upcoming_events(user_id, days)
        if events:
            reply = f"📅 На ближайшие {days} дней у Вас следующие планы:\n" + "\n".join(
                [f"{e['event_date'].strftime('%d.%m %H:%M')} {e['event_name']}" for e in events])
        else:
            reply = "📭 Нет запланированных событий."
        await update.message.reply_text(reply)
        return

    # ========== 3. УДАЛЕНИЕ ЗАПИСИ ==========
    match = re.match(r"отмени запись (.+)", text_lower)
    if match:
        event_name = match.group(1).strip()
        deleted = delete_event(user_id, event_name)
        if deleted:
            await update.message.reply_text(f"🗑️ Запись '{event_name}' удалена!")
        else:
            await update.message.reply_text("❗ Такой записи не существует, ознакомьтесь со списком и попробуйте ещё раз.")
        return

    # ========== 4. ДОБАВЛЕНИЕ ЗАМЕТКИ ==========
    match = re.match(r"(создай|запиши) заметку[,:]?\s*(.+?):\s*(.+?)(?: с тегом (.+))?$", text_lower)
    if match:
        name = match.group(2).strip().capitalize()
        content = match.group(3).strip()
        tag = match.group(4).strip() if match.group(4) else ""
        add_note(user_id, name, content, [tag] if tag else [])
        reply = f"📝 Заметка с названием '{name}'"
        if tag:
            reply += f" и тегом '{tag}'"
        reply += " успешно создана!"
        await update.message.reply_text(reply)
        return

    # ========== 5. ПРОСМОТР ЗАМЕТОК ПО ТЕГУ ==========
    match = re.match(r"покажи список заметок с тегом (.+)", text_lower)
    if match:
        tag = match.group(1).strip()
        notes = get_notes_by_tag(user_id, tag)
        if notes:
            note_list = "\n".join([f"- {n['note_name']}" for n in notes])
            await update.message.reply_text(f"📚 Вот список заметок с тегом '{tag}':\n{note_list}")
        else:
            await update.message.reply_text("📭 С указанным тегом пока что нет заметок :")
        return

    # ========== 6. ОТКРЫТИЕ ЗАМЕТКИ ==========
    match = re.match(r"открой содержимое заметки (.+)", text_lower)
    if match:
        name = match.group(1).strip()
        note = get_note_by_name(user_id, name)
        if note:
            tag_part = f"\n#{note['tag']}" if note.get("tag") else ""
            await update.message.reply_text(f"{note['note_name']}\n{note['note_content']}{tag_part}")
        else:
            await update.message.reply_text(f"❗ К сожалению я не могу найти заметку с таким названием: {name}")
        return

    # ========== 7. УДАЛЕНИЕ ЗАМЕТКИ ==========
    match = re.match(r"удали заметку (.+)", text_lower)
    if match:
        name = match.group(1).strip()
        deleted = delete_note(user_id, name)
        if deleted:
            await update.message.reply_text(f"🗑️ Заметка с названием '{name}' успешно удалена.")
        else:
            await update.message.reply_text("❗ К сожалению такой заметки не существует.")
        return

    # ========== 8. ПЕРЕИМЕНОВАНИЕ ЗАМЕТКИ ==========
    match = re.match(r"переименуй заметку (.+?) на (.+)", text_lower)
    if match:
        old_name = match.group(1).strip()
        new_name = match.group(2).strip()
        renamed = rename_note(user_id, old_name, new_name)
        if renamed:
            await update.message.reply_text(f"✏️ Заметка '{old_name}' успешно переименована на '{new_name}'.")
        else:
            await update.message.reply_text("❗ Не удалось переименовать: такой заметки не существует.")
        return

    # ========== НЕИЗВЕСТНАЯ КОМАНДА ==========
    await update.message.reply_text("🤖 Я не понял ваш запрос. Попробуйте использовать шаблонную команду.")

# =============================== ЗАПУСК ===============================
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()