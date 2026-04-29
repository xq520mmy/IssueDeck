"""item events timeline

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "item_pk",
            sa.Integer,
            sa.ForeignKey("items.pk", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_name", sa.String(128), nullable=False),
        sa.Column("body", sa.Text, nullable=False, server_default=""),
        sa.Column("metadata_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index(
        "ix_item_events_item_created",
        "item_events",
        ["item_pk", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_item_events_item_created", table_name="item_events")
    op.drop_table("item_events")
