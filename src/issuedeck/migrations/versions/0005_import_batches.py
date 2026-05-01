"""import batch history

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_key", sa.String(128), nullable=False),
        sa.Column("batch_tag", sa.String(128), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_name", sa.Text, nullable=False, server_default=""),
        sa.Column("items_planned", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_written", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status_mapped", sa.Integer, nullable=False, server_default="0"),
        sa.Column("external_links", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("metadata_json", sa.Text, nullable=False, server_default="{}"),
        sa.UniqueConstraint(
            "project_key",
            "batch_tag",
            name="uq_import_batches_project_batch",
        ),
    )
    op.create_index(
        "ix_import_batches_project_created",
        "import_batches",
        ["project_key", "created_at"],
    )
    op.create_index(
        "ix_import_batches_project_source",
        "import_batches",
        ["project_key", "source_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_import_batches_project_source", table_name="import_batches")
    op.drop_index("ix_import_batches_project_created", table_name="import_batches")
    op.drop_table("import_batches")
