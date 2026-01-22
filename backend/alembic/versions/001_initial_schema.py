"""Initial schema - baseline of existing database structure

Revision ID: 001
Revises: None
Create Date: 2025-01-21

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check if tasks table exists
    result = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    ).fetchone()

    if not result:
        # Create tasks table from scratch
        conn.execute(text("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                task_key TEXT NOT NULL,
                category TEXT NOT NULL,
                task_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                scheduled_date TEXT,
                recurrence_rule TEXT,
                created_at TEXT NOT NULL
            )
        """))
    else:
        # Migrate existing table if needed
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()}

        if "task_key" not in columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN task_key TEXT"))
            conn.execute(text("ALTER TABLE tasks ADD COLUMN category TEXT DEFAULT 'T'"))
            conn.execute(text("ALTER TABLE tasks ADD COLUMN task_number INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE tasks ADD COLUMN scheduled_date TEXT"))
            # Update existing tasks with T-## keys
            rows = conn.execute(text("SELECT id FROM tasks ORDER BY created_at")).fetchall()
            for i, row in enumerate(rows, start=1):
                conn.execute(
                    text("UPDATE tasks SET task_key = :key, category = 'T', task_number = :num WHERE id = :id"),
                    {"key": f"T-{i:02d}", "num": i, "id": row[0]}
                )

        if "recurrence_rule" not in columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN recurrence_rule TEXT"))

    # Create category_sequences table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS category_sequences (
            category TEXT PRIMARY KEY,
            next_number INTEGER DEFAULT 1
        )
    """))

    # Create conversations table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            messages TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS conversations"))
    conn.execute(text("DROP TABLE IF EXISTS category_sequences"))
    conn.execute(text("DROP TABLE IF EXISTS tasks"))
