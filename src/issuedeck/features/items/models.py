"""All SQLAlchemy ORM models.

Kept in one file because the schema is interrelated (every join table points
back to `items.pk`) and Alembic autogenerate wants them registered on a single
`Base.metadata`. Feature packages like `relationships/` and `search/` import
from here rather than define their own ORM.

Column types follow SQLite's affinity rules — BigInteger maps to INTEGER,
string types map to TEXT, booleans are stored as integers. All timestamps are
ISO-8601 strings in UTC (so sorts, comparisons, and JSON round-trips are all
lexicographic and consistent).
"""

from __future__ import annotations

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_key: Mapped[str] = mapped_column(String(128), nullable=False)
    local_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    custom_fields_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40), nullable=True)

    tags: Mapped[list[ItemTag]] = relationship(
        back_populates="item", cascade="all, delete-orphan",
    )
    applies_to: Mapped[list[ItemApplyTo]] = relationship(
        back_populates="item", cascade="all, delete-orphan",
    )
    ship_records: Mapped[list[ShipRecord]] = relationship(
        back_populates="item", cascade="all, delete-orphan",
    )
    events: Mapped[list[ItemEvent]] = relationship(
        back_populates="item", cascade="all, delete-orphan",
    )
    external_links: Mapped[list[ItemExternalLink]] = relationship(
        back_populates="item", cascade="all, delete-orphan",
        order_by="ItemExternalLink.id",
    )
    work_sessions: Mapped[list[WorkSession]] = relationship(
        back_populates="item",
        order_by="WorkSession.updated_at.desc()",
    )

    __table_args__ = (
        UniqueConstraint("project_key", "local_id", name="uq_items_project_local"),
        Index("ix_items_project_status_updated",
              "project_key", "status", "updated_at"),
        Index("ix_items_project_kind", "project_key", "kind"),
        # Partial-index predicate `WHERE deleted_at IS NULL` is added by the
        # Alembic migration in Task 8; SQLAlchemy's Index() alone can't emit it.
        Index("ix_items_project_active_updated",
              "project_key", "updated_at"),
    )


class ItemTag(Base):
    __tablename__ = "item_tags"

    item_pk: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.pk", ondelete="CASCADE"), primary_key=True,
    )
    tag: Mapped[str] = mapped_column(String(128), primary_key=True)
    item: Mapped[Item] = relationship(back_populates="tags")

    __table_args__ = (
        Index("ix_item_tags_tag_item", "tag", "item_pk"),
    )


class ItemApplyTo(Base):
    __tablename__ = "item_applies_to"

    item_pk: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.pk", ondelete="CASCADE"), primary_key=True,
    )
    branch_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    item: Mapped[Item] = relationship(back_populates="applies_to")


class ItemExternalLink(Base):
    __tablename__ = "item_external_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_pk: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.pk", ondelete="CASCADE"), nullable=False,
    )
    link_type: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    item: Mapped[Item] = relationship(back_populates="external_links")

    __table_args__ = (
        UniqueConstraint("item_pk", "url", name="uq_item_external_links_item_url"),
        Index("ix_item_external_links_item_type", "item_pk", "link_type"),
    )


class ShipRecord(Base):
    __tablename__ = "ship_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_pk: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.pk", ondelete="CASCADE"), nullable=False,
    )
    branch_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    shipped_at: Mapped[str] = mapped_column(String(40), nullable=False)

    item: Mapped[Item] = relationship(back_populates="ship_records")
    commits: Mapped[list[ShipCommit]] = relationship(
        back_populates="ship_record", cascade="all, delete-orphan",
        order_by="ShipCommit.position",
    )

    __table_args__ = (
        UniqueConstraint("item_pk", "branch_key", name="uq_ship_item_branch"),
    )


class ShipCommit(Base):
    __tablename__ = "ship_commits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ship_record_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ship_records.id", ondelete="CASCADE"), nullable=False,
    )
    sha: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    ship_record: Mapped[ShipRecord] = relationship(back_populates="commits")

    __table_args__ = (
        Index("ix_ship_commits_record_pos", "ship_record_id", "position"),
    )


class ItemEvent(Base):
    __tablename__ = "item_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_pk: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.pk", ondelete="CASCADE"), nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    item: Mapped[Item] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_item_events_item_created", "item_pk", "created_at"),
    )


class WorkSession(Base):
    __tablename__ = "work_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_key: Mapped[str] = mapped_column(String(128), nullable=False)
    item_pk: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("items.pk", ondelete="SET NULL"), nullable=True,
    )
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    branch: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    ended_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    item: Mapped[Item | None] = relationship(back_populates="work_sessions")
    updates: Mapped[list[WorkSessionUpdate]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="WorkSessionUpdate.created_at",
    )

    __table_args__ = (
        Index(
            "ix_work_sessions_project_status_updated",
            "project_key",
            "status",
            "updated_at",
        ),
        Index("ix_work_sessions_item_updated", "item_pk", "updated_at"),
        Index("ix_work_sessions_agent_status", "agent_name", "status"),
    )


class WorkSessionUpdate(Base):
    __tablename__ = "work_session_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("work_sessions.id", ondelete="CASCADE"), nullable=False,
    )
    update_type: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    session: Mapped[WorkSession] = relationship(back_populates="updates")

    __table_args__ = (
        Index("ix_work_session_updates_session_created", "session_id", "created_at"),
    )


class ItemRelationship(Base):
    __tablename__ = "item_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_item_pk: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.pk", ondelete="CASCADE"), nullable=False,
    )
    to_item_pk: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.pk", ondelete="CASCADE"), nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (
        UniqueConstraint("from_item_pk", "to_item_pk", "relation_type",
                         name="uq_rel_from_to_type"),
        Index("ix_rel_to_type", "to_item_pk", "relation_type"),
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_key: Mapped[str] = mapped_column(String(128), nullable=False)
    batch_tag: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    items_planned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_mapped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    external_links: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    __table_args__ = (
        UniqueConstraint("project_key", "batch_tag", name="uq_import_batches_project_batch"),
        Index("ix_import_batches_project_created", "project_key", "created_at"),
        Index("ix_import_batches_project_source", "project_key", "source_type"),
    )
