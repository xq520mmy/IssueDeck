"""agent work sessions

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_key", sa.String(128), nullable=False),
        sa.Column(
            "item_pk",
            sa.Integer,
            sa.ForeignKey("items.pk", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("goal", sa.Text, nullable=False, server_default=""),
        sa.Column("summary", sa.Text, nullable=False, server_default=""),
        sa.Column("branch", sa.String(128), nullable=True),
        sa.Column("started_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("ended_at", sa.String(40), nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=False, server_default="{}"),
    )
    op.create_index(
        "ix_work_sessions_project_status_updated",
        "work_sessions",
        ["project_key", "status", "updated_at"],
    )
    op.create_index(
        "ix_work_sessions_item_updated",
        "work_sessions",
        ["item_pk", "updated_at"],
    )
    op.create_index(
        "ix_work_sessions_agent_status",
        "work_sessions",
        ["agent_name", "status"],
    )

    op.create_table(
        "work_session_updates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer,
            sa.ForeignKey("work_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("update_type", sa.String(32), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("metadata_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index(
        "ix_work_session_updates_session_created",
        "work_session_updates",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_work_session_updates_session_created",
        table_name="work_session_updates",
    )
    op.drop_table("work_session_updates")
    op.drop_index("ix_work_sessions_agent_status", table_name="work_sessions")
    op.drop_index("ix_work_sessions_item_updated", table_name="work_sessions")
    op.drop_index(
        "ix_work_sessions_project_status_updated",
        table_name="work_sessions",
    )
    op.drop_table("work_sessions")
