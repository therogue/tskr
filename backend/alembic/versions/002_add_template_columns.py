"""Add is_template and parent_task_id columns for recurring task templates

Revision ID: 002
Revises: 001
Create Date: 2025-02-05

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check existing columns
    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()}

    if "is_template" not in columns:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN is_template INTEGER DEFAULT 0"))

    if "parent_task_id" not in columns:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN parent_task_id TEXT"))


def downgrade() -> None:
    # SQLite doesn't support DROP COLUMN easily, so we'd need to recreate the table
    # For simplicity, downgrade is a no-op (columns remain but are unused)
    pass
