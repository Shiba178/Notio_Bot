import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
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

def add_event(user_id, event_name, event_date, remind_before):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO events (user_id, event_name, event_date, remind_before) VALUES (%s, %s, %s, %s);",
                (user_id, event_name, event_date, remind_before)
            )
            conn.commit()

def get_upcoming_events(user_id, days=7):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM events WHERE user_id = %s AND event_date BETWEEN NOW() AND NOW() + interval %s ORDER BY event_date;",
                (user_id, f'{days} days')
            )
            return cur.fetchall()

def add_note(user_id, note_name, note_content, tags):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO notes (user_id, note_name, note_content, tags) VALUES (%s, %s, %s, %s);",
                (user_id, note_name, note_content, tags)
            )
            conn.commit()

def get_notes_by_tag(user_id, tag):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM notes WHERE user_id = %s AND %s = ANY(tags);",
                (user_id, tag)
            )
            return cur.fetchall()

def get_note_by_name(user_id, note_name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM notes WHERE user_id = %s AND LOWER(note_name) = LOWER(%s) LIMIT 1;",
                (user_id, note_name)
            )
            return cur.fetchone()