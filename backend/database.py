import sqlite3
import json
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

DATABASE_PATH = "deskbot.db"

@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize database tables."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        # Single conversation for now; id=1 is the active conversation
        # messages stored as JSON array
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                messages TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()

# Task operations
def get_all_tasks() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "completed": bool(row["completed"]),
                "created_at": row["created_at"]
            }
            for row in rows
        ]

def create_task_db(task_id: str, title: str) -> dict:
    created_at = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO tasks (id, title, completed, created_at) VALUES (?, ?, 0, ?)",
            (task_id, title, created_at)
        )
        conn.commit()
    return {"id": task_id, "title": title, "completed": False, "created_at": created_at}

def update_task_db(task_id: str, title: Optional[str] = None, completed: Optional[bool] = None) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None

        new_title = title if title is not None else row["title"]
        new_completed = int(completed) if completed is not None else row["completed"]

        conn.execute(
            "UPDATE tasks SET title = ?, completed = ? WHERE id = ?",
            (new_title, new_completed, task_id)
        )
        conn.commit()
        return {"id": task_id, "title": new_title, "completed": bool(new_completed), "created_at": row["created_at"]}

def delete_task_db(task_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0

def find_task_by_title_db(title: str) -> Optional[dict]:
    """Find a task by partial title match (case-insensitive)."""
    title_lower = title.lower()
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
        for row in rows:
            if title_lower in row["title"].lower():
                return {
                    "id": row["id"],
                    "title": row["title"],
                    "completed": bool(row["completed"]),
                    "created_at": row["created_at"]
                }
    return None

# Conversation operations
def get_conversation() -> list[dict]:
    """Get the current conversation messages."""
    with get_db() as conn:
        row = conn.execute("SELECT messages FROM conversations WHERE id = 1").fetchone()
        if row:
            return json.loads(row["messages"])
        return []

def save_conversation(messages: list[dict]):
    """Save conversation messages."""
    now = datetime.now().isoformat()
    messages_json = json.dumps(messages)
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM conversations WHERE id = 1").fetchone()
        if existing:
            conn.execute(
                "UPDATE conversations SET messages = ?, updated_at = ? WHERE id = 1",
                (messages_json, now)
            )
        else:
            conn.execute(
                "INSERT INTO conversations (id, messages, created_at, updated_at) VALUES (1, ?, ?, ?)",
                (messages_json, now, now)
            )
        conn.commit()
