"""Notices, each kept as one document with the columns queries need beside it.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notices",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=False),
        sa.Column("number", sa.Text, nullable=False),
        sa.Column("version", sa.BigInteger, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("buyer_name", sa.Text, nullable=False),
        sa.Column("published_on", sa.Date, nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cpv_codes", postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column("body", postgresql.JSONB, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("notices_cpv_codes", "notices", ["cpv_codes"], postgresql_using="gin")
    op.create_index("notices_deadline", "notices", ["deadline"])


def downgrade() -> None:
    op.drop_table("notices")
