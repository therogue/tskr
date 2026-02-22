"""Add priority column for task priority scoring

Revision ID: 004
Revises: 003
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check existing columns
    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()}

    if "priority" not in columns:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN priority INTEGER"))


def downgrade() -> None:
    # SQLite doesn't support DROP COLUMN easily; downgrade is a no-op
    pass
