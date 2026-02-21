"""Add title column to conversations for multi-conversation support

Revision ID: 004
Revises: 003
Create Date: 2026-02-21

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

    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(conversations)")).fetchall()}

    if "title" not in columns:
        conn.execute(text("ALTER TABLE conversations ADD COLUMN title TEXT DEFAULT 'Untitled'"))


def downgrade() -> None:
    pass
