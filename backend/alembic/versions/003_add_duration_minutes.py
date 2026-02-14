"""Add duration_minutes column for task duration tracking

Revision ID: 003
Revises: 002
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check existing columns
    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()}

    if "duration_minutes" not in columns:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN duration_minutes INTEGER"))


def downgrade() -> None:
    # SQLite doesn't support DROP COLUMN easily; downgrade is a no-op
    pass
