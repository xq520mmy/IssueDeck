"""item external links

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_external_links",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "item_pk",
            sa.Integer,
            sa.ForeignKey("items.pk", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("link_type", sa.String(32), nullable=False),
        sa.Column("label", sa.String(160), nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("item_pk", "url", name="uq_item_external_links_item_url"),
    )
    op.create_index(
        "ix_item_external_links_item_type",
        "item_external_links",
        ["item_pk", "link_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_item_external_links_item_type", table_name="item_external_links")
    op.drop_table("item_external_links")
