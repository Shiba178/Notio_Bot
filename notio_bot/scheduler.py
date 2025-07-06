from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from db import get_conn
import telegram
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telegram.Bot(TELEGRAM_TOKEN)

def send_reminders():
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()
    cur.execute("""
        SELECT id, user_id, event_name, event_date, remind_before FROM events
        WHERE event_date - interval '1 hour' * remind_before BETWEEN %s AND %s;
    """, (now, now + timedelta(minutes=1)))
    reminders = cur.fetchall()
    for r in reminders:
        message = f"🔔 Напоминание: {r['event_name']} запланировано на {r['event_date']}."
        bot.send_message(chat_id=r['user_id'], text=message)
    cur.close()
    conn.close()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_reminders, 'interval', minutes=1)
    scheduler.start()
