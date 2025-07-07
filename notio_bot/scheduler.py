from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from db import get_conn
from telegram import Bot
import os
import logging

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)

def send_reminders():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                now = datetime.now()
                cur.execute("""
                    SELECT user_id, event_name, event_date FROM events
                    WHERE event_date - interval '1 hour' * remind_before BETWEEN %s AND %s;
                """, (now, now + timedelta(minutes=1)))
                reminders = cur.fetchall()

                for r in reminders:
                    message = f"🔔 Напоминание: {r['event_name']} запланировано на {r['event_date']}."
                    bot.send_message(chat_id=r['user_id'], text=message)
    except Exception as e:
        logging.error(f"[SCHEDULER ERROR] {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_reminders, 'interval', minutes=1)
    scheduler.start()