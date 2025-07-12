import psycopg2
import psycopg2.extras
import os
from datetime import datetime

DB_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)

# ==================== Инициализация базы ====================
def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Таблица событий (календарь)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    event_name TEXT,
                    event_date TIMESTAMP,
                    remind_before INTEGER
                );
            """)
            # Таблица заметок
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    note_name TEXT,
                    note_content TEXT,
                    tag TEXT
                );
            """)
            conn.commit()

# ==================== Работа с календарем ====================
def add_event(user_id, name, date, remind_before):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO events (user_id, event_name, event_date, remind_before)
                VALUES (%s, %s, %s, %s);
            """, (user_id, name, date, remind_before))
            conn.commit()

def get_upcoming_events(user_id, days=7):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT event_name, event_date FROM events
                WHERE user_id = %s AND event_date >= NOW() AND event_date <= NOW() + interval '%s days'
                ORDER BY event_date;
            """, (user_id, days))
            return cur.fetchall()

def delete_event(user_id, name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM events
                WHERE user_id = %s AND LOWER(event_name) = LOWER(%s)
                RETURNING *;
            """, (user_id, name))
            deleted = cur.fetchone()
            conn.commit()
            return deleted is not None

# ==================== Работа с заметками ====================
def add_note(user_id, name, content, tags):
    try:
        tag = str(tags[0]) if tags and isinstance(tags[0], str) else None
        print(f"DEBUG >> add_note: user_id={user_id}, name={name}, content={content}, tag={tag}")
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO notes (user_id, note_name, note_content, tag)
                    VALUES (%s, %s, %s, %s);
                """, (user_id, name, content, tag))
                conn.commit()
    except Exception as e:
        print(f"[DB ERROR] add_note: {e}")
        raise

def get_notes_by_tag(user_id, tag):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT note_name FROM notes
                WHERE user_id = %s AND LOWER(tag) = LOWER(%s);
            """, (user_id, tag))
            return cur.fetchall()

def get_note_by_name(user_id, name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT note_name, note_content, tag FROM notes
                WHERE user_id = %s AND LOWER(note_name) = LOWER(%s);
            """, (user_id, name))
            return cur.fetchone()

def delete_note(user_id, name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM notes
                WHERE user_id = %s AND LOWER(note_name) = LOWER(%s)
                RETURNING *;
            """, (user_id, name))
            deleted = cur.fetchone()
            conn.commit()
            return deleted is not None

def rename_note(user_id, old_name, new_name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE notes
                SET note_name = %s
                WHERE user_id = %s AND LOWER(note_name) = LOWER(%s)
                RETURNING *;
            """, (new_name, user_id, old_name))
            updated = cur.fetchone()
            conn.commit()
            return updated is not None