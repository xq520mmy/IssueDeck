"""initial schema — items, joins, ship, relationships, fts5 virtual + triggers

Revision ID: 0001
Revises:
Create Date: 2026-04-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("pk", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_key", sa.String(128), nullable=False),
        sa.Column("local_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("deleted_at", sa.String(40), nullable=True),
        sa.UniqueConstraint("project_key", "local_id", name="uq_items_project_local"),
    )
    op.create_index("ix_items_project_status_updated", "items",
                    ["project_key", "status", "updated_at"])
    op.create_index("ix_items_project_kind", "items", ["project_key", "kind"])
    op.execute(
        "CREATE INDEX ix_items_project_active_updated "
        "ON items (project_key, updated_at DESC) WHERE deleted_at IS NULL"
    )

    op.create_table(
        "item_tags",
        sa.Column("item_pk", sa.Integer,
                  sa.ForeignKey("items.pk", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag", sa.String(128), primary_key=True),
    )
    op.create_index("ix_item_tags_tag_item", "item_tags", ["tag", "item_pk"])

    op.create_table(
        "item_applies_to",
        sa.Column("item_pk", sa.Integer,
                  sa.ForeignKey("items.pk", ondelete="CASCADE"), primary_key=True),
        sa.Column("branch_key", sa.String(64), primary_key=True),
    )

    op.create_table(
        "ship_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("item_pk", sa.Integer,
                  sa.ForeignKey("items.pk", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_key", sa.String(64), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("shipped_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("item_pk", "branch_key", name="uq_ship_item_branch"),
    )

    op.create_table(
        "ship_commits",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ship_record_id", sa.Integer,
                  sa.ForeignKey("ship_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sha", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
    )
    op.create_index("ix_ship_commits_record_pos", "ship_commits",
                    ["ship_record_id", "position"])

    op.create_table(
        "item_relationships",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("from_item_pk", sa.Integer,
                  sa.ForeignKey("items.pk", ondelete="CASCADE"), nullable=False),
        sa.Column("to_item_pk", sa.Integer,
                  sa.ForeignKey("items.pk", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("from_item_pk", "to_item_pk", "relation_type",
                            name="uq_rel_from_to_type"),
    )
    op.create_index("ix_rel_to_type", "item_relationships",
                    ["to_item_pk", "relation_type"])

    op.execute("""
        CREATE VIRTUAL TABLE items_fts USING fts5(
            title, body,
            content='items',
            content_rowid='pk',
            tokenize='porter unicode61'
        )
    """)
    op.execute("""
        CREATE TRIGGER items_fts_ai AFTER INSERT ON items BEGIN
          INSERT INTO items_fts(rowid, title, body)
          VALUES (new.pk, new.title, new.body);
        END
    """)
    op.execute("""
        CREATE TRIGGER items_fts_ad AFTER DELETE ON items BEGIN
          INSERT INTO items_fts(items_fts, rowid, title, body)
          VALUES('delete', old.pk, old.title, old.body);
        END
    """)
    op.execute("""
        CREATE TRIGGER items_fts_au AFTER UPDATE ON items BEGIN
          INSERT INTO items_fts(items_fts, rowid, title, body)
          VALUES('delete', old.pk, old.title, old.body);
          INSERT INTO items_fts(rowid, title, body)
          VALUES (new.pk, new.title, new.body);
        END
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS items_fts_au")
    op.execute("DROP TRIGGER IF EXISTS items_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS items_fts_ai")
    op.execute("DROP TABLE IF EXISTS items_fts")
    op.drop_table("item_relationships")
    op.drop_table("ship_commits")
    op.drop_table("ship_records")
    op.drop_table("item_applies_to")
    op.drop_table("item_tags")
    op.drop_table("items")
