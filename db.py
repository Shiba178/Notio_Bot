import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        event_name TEXT,
        event_date TIMESTAMP,
        remind_before INTEGER DEFAULT 24
    );
    CREATE TABLE IF NOT EXISTS notes (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        note_name TEXT,
        note_content TEXT,
        tags TEXT[]
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

def add_event(user_id, event_name, event_date, remind_before):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO events (user_id, event_name, event_date, remind_before) VALUES (%s,%s,%s,%s);",
        (user_id, event_name, event_date, remind_before)
    )
    conn.commit()
    cur.close()
    conn.close()

def get_upcoming_events(user_id, days=7):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM events WHERE user_id=%s AND event_date BETWEEN NOW() AND NOW() + interval '%s days' ORDER BY event_date;",
        (user_id, days)
    )
    events = cur.fetchall()
    cur.close()
    conn.close()
    return events

def add_note(user_id, note_name, note_content, tags):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO notes (user_id, note_name, note_content, tags) VALUES (%s,%s,%s,%s);",
        (user_id, note_name, note_content, tags)
    )
    conn.commit()
    cur.close()
    conn.close()

def get_notes_by_tag(user_id, tag):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM notes WHERE user_id=%s AND %s=ANY(tags);",
        (user_id, tag)
    )
    notes = cur.fetchall()
    cur.close()
    conn.close()
    return notes

def get_note_by_name(user_id, note_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM notes WHERE user_id=%s AND LOWER(note_name)=LOWER(%s) LIMIT 1;",
        (user_id, note_name)
    )
    note = cur.fetchone()
    cur.close()
    conn.close()
    return note
