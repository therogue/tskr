"""Add user_settings table for configurable defaults

Revision ID: 006
Revises: f20394fbccdd
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = '006'
down_revision: Union[str, None] = 'f20394fbccdd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
    if "user_settings" not in tables:
        conn.execute(text(
            "CREATE TABLE user_settings ("
            "id VARCHAR NOT NULL, "
            "default_category VARCHAR NOT NULL DEFAULT 'T', "
            "default_priority VARCHAR NOT NULL DEFAULT 'medium', "
            "conflict_resolution VARCHAR NOT NULL DEFAULT 'overlap', "
            "PRIMARY KEY (id)"
            ")"
        ))
    else:
        # If table was previously created with INTEGER default_priority, convert to names
        conn.execute(text(
            "UPDATE user_settings SET default_priority = CASE CAST(default_priority AS INTEGER) "
            "WHEN 0 THEN 'none' WHEN 1 THEN 'low' WHEN 2 THEN 'medium' "
            "WHEN 3 THEN 'high' WHEN 4 THEN 'critical' ELSE default_priority END "
            "WHERE typeof(default_priority) = 'integer'"
        ))


def downgrade() -> None:
    # SQLite DROP TABLE is supported but skipped to preserve user data
    pass
