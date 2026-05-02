"""ItemRepo — data access for the items feature.

Returns ORM instances to the service layer. Does not commit — the service layer
owns transaction boundaries so ship_item (item + ship_record + ship_commits)
lands atomically.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import Float, Integer, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from issuedeck.features.items.custom_fields import CustomFieldFilter
from issuedeck.features.items.models import (
    Item,
    ItemApplyTo,
    ItemEvent,
    ItemExternalLink,
    ItemRelationship,
    ItemTag,
    ShipCommit,
    ShipRecord,
)


class ItemRepo:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def next_local_id(
        self, project_key: str, *, kind: str, prefix: str, digits: int,
    ) -> str:
        """Compute the next local_id for (project_key, kind).

        The caller must be inside a BEGIN IMMEDIATE transaction so concurrent
        writers are serialized and MAX(local_id) stays consistent with the
        subsequent INSERT.
        """
        # SUBSTR(local_id, LENGTH(prefix) + 2) strips "PREFIX-" and parses the
        # numeric tail. Because prefixes are unique per kind we only need to
        # filter by (project_key, kind).
        stmt = select(
            func.max(
                func.cast(
                    func.substr(Item.local_id, len(prefix) + 2),
                    type_=Integer,
                )
            )
        ).where(Item.project_key == project_key, Item.kind == kind)
        result = await self._s.execute(stmt)
        current = result.scalar() or 0
        return f"{prefix}-{(current + 1):0{digits}d}"

    async def insert_item(
        self, *, project_key: str, local_id: str, kind: str, status: str,
        title: str, body: str, tags: list[str], applies_to: list[str],
        custom_fields_json: str = "{}",
        external_links: list[dict[str, str | None]] | None = None,
        created_at: str | None = None, updated_at: str | None = None,
    ) -> Item:
        now = created_at or _iso_now()
        item = Item(
            project_key=project_key, local_id=local_id,
            kind=kind, status=status, title=title, body=body,
            custom_fields_json=custom_fields_json,
            created_at=now, updated_at=updated_at or now,
        )
        self._s.add(item)
        await self._s.flush()
        for t in tags:
            self._s.add(ItemTag(item_pk=item.pk, tag=t))
        for b in applies_to:
            self._s.add(ItemApplyTo(item_pk=item.pk, branch_key=b))
        self._add_external_links(item.pk, external_links or [], created_at=now)
        await self._s.flush()
        return item

    async def get_by_local_id(
        self, project_key: str, local_id: str, *, include_deleted: bool = False,
    ) -> Item | None:
        stmt = select(Item).where(
            Item.project_key == project_key, Item.local_id == local_id,
        )
        if not include_deleted:
            stmt = stmt.where(Item.deleted_at.is_(None))
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def update_item_fields(
        self, item: Item, *, title: str | None = None, body: str | None = None,
        kind: str | None = None, status: str | None = None, tags: list[str] | None = None,
        applies_to: list[str] | None = None,
        custom_fields_json: str | None = None,
        external_links: list[dict[str, str | None]] | None = None,
    ) -> None:
        if title is not None:
            item.title = title
        if body is not None:
            item.body = body
        if kind is not None:
            item.kind = kind
        if status is not None:
            item.status = status
        if custom_fields_json is not None:
            item.custom_fields_json = custom_fields_json
        if tags is not None:
            item.tags.clear()
            for t in tags:
                item.tags.append(ItemTag(item_pk=item.pk, tag=t))
        if applies_to is not None:
            item.applies_to.clear()
            for b in applies_to:
                item.applies_to.append(ItemApplyTo(item_pk=item.pk, branch_key=b))
        if external_links is not None:
            timestamp = _iso_now()
            item.external_links.clear()
            for link in external_links:
                item.external_links.append(ItemExternalLink(
                    item_pk=item.pk,
                    link_type=str(link["link_type"]),
                    label=link.get("label") or None,
                    url=str(link["url"]),
                    created_at=timestamp,
                ))
        item.updated_at = _iso_now()
        await self._s.flush()

    async def soft_delete(self, pk: int, *, deleted_at: str) -> None:
        await self._s.execute(
            update(Item).where(Item.pk == pk).values(
                deleted_at=deleted_at, updated_at=deleted_at,
            )
        )

    async def restore(self, pk: int) -> None:
        await self._s.execute(
            update(Item).where(Item.pk == pk).values(
                deleted_at=None, updated_at=_iso_now(),
            )
        )

    async def upsert_ship_record(
        self, *, item_pk: int, branch_key: str, version: str,
        shipped_at: str, commits: list[str],
    ) -> ShipRecord:
        existing = (await self._s.execute(
            select(ShipRecord)
            .where(
                ShipRecord.item_pk == item_pk,
                ShipRecord.branch_key == branch_key,
            )
            .options(selectinload(ShipRecord.commits))
        )).scalar_one_or_none()
        if existing is None:
            sr = ShipRecord(item_pk=item_pk, branch_key=branch_key,
                            version=version, shipped_at=shipped_at)
            self._s.add(sr)
            await self._s.flush()
            # New record — no prior commits; start at position 0.
            start = 0
        else:
            existing.version = version
            existing.shipped_at = shipped_at
            sr = existing
            # existing was loaded with selectinload(commits) so no lazy load here.
            existing_positions = [c.position for c in sr.commits]
            start = (max(existing_positions) + 1) if existing_positions else 0

        for i, sha in enumerate(commits):
            self._s.add(ShipCommit(
                ship_record_id=sr.id, sha=sha, position=start + i,
            ))
        await self._s.flush()
        return sr

    async def add_event(
        self, *, item_pk: int, event_type: str, actor_type: str,
        actor_name: str, body: str, metadata_json: str, created_at: str,
    ) -> ItemEvent:
        event = ItemEvent(
            item_pk=item_pk,
            event_type=event_type,
            actor_type=actor_type,
            actor_name=actor_name,
            body=body,
            metadata_json=metadata_json,
            created_at=created_at,
        )
        self._s.add(event)
        await self._s.flush()
        return event

    async def list_events(self, item_pk: int, *, limit: int = 100) -> list[ItemEvent]:
        stmt = (
            select(ItemEvent)
            .where(ItemEvent.item_pk == item_pk)
            .order_by(ItemEvent.created_at.desc(), ItemEvent.id.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def list_by_local_ids(
        self,
        project_key: str,
        local_ids: list[str],
        *,
        include_deleted: bool = False,
    ) -> list[Item]:
        stmt = (
            select(Item)
            .where(Item.project_key == project_key, Item.local_id.in_(local_ids))
            .options(
                selectinload(Item.tags),
                selectinload(Item.applies_to),
                selectinload(Item.external_links),
            )
        )
        if not include_deleted:
            stmt = stmt.where(Item.deleted_at.is_(None))
        return list((await self._s.execute(stmt)).scalars().all())

    def _add_external_links(
        self,
        item_pk: int,
        links: list[dict[str, str | None]],
        *,
        created_at: str | None = None,
    ) -> None:
        timestamp = created_at or _iso_now()
        for link in links:
            self._s.add(ItemExternalLink(
                item_pk=item_pk,
                link_type=str(link["link_type"]),
                label=link.get("label") or None,
                url=str(link["url"]),
                created_at=timestamp,
            ))

    async def list_items(
        self,
        project_key: str,
        *,
        kinds: list[str] | None = None,
        statuses: list[str] | None = None,
        applies_to: list[str] | None = None,
        shipped_in_branch: str | None = None,
        shipped_in_version: str | None = None,
        tags: list[str] | None = None,
        relationship_types: list[str] | None = None,
        custom_fields: list[CustomFieldFilter] | None = None,
        since: str | None = None,
        include_deleted: bool = False,
        only_deleted: bool = False,
        limit: int = 50,
        after_updated_at: str | None = None,
        after_pk: int | None = None,
    ) -> list[Item]:
        from sqlalchemy import tuple_

        stmt = select(Item).where(Item.project_key == project_key)
        if only_deleted:
            stmt = stmt.where(Item.deleted_at.is_not(None))
        elif not include_deleted:
            stmt = stmt.where(Item.deleted_at.is_(None))
        if kinds:
            stmt = stmt.where(Item.kind.in_(kinds))
        if statuses:
            stmt = stmt.where(Item.status.in_(statuses))
        if since:
            stmt = stmt.where(Item.updated_at >= since)
        if tags:
            for t in tags:
                stmt = stmt.where(
                    Item.pk.in_(select(ItemTag.item_pk).where(ItemTag.tag == t))
                )
        if custom_fields:
            for field_filter in custom_fields:
                stmt = stmt.where(_custom_field_where(field_filter))
        if applies_to:
            stmt = stmt.where(
                Item.pk.in_(select(ItemApplyTo.item_pk).where(
                    ItemApplyTo.branch_key.in_(applies_to)
                ))
            )
        if relationship_types:
            stmt = stmt.where(
                Item.pk.in_(select(ItemRelationship.from_item_pk).where(
                    ItemRelationship.relation_type.in_(relationship_types)
                ))
            )
        if shipped_in_branch:
            sq = select(ShipRecord.item_pk).where(
                ShipRecord.branch_key == shipped_in_branch
            )
            if shipped_in_version:
                sq = sq.where(ShipRecord.version == shipped_in_version)
            stmt = stmt.where(Item.pk.in_(sq))
        elif shipped_in_version:
            stmt = stmt.where(
                Item.pk.in_(select(ShipRecord.item_pk).where(
                    ShipRecord.version == shipped_in_version
                ))
            )

        if after_updated_at is not None and after_pk is not None:
            stmt = stmt.where(
                tuple_(Item.updated_at, Item.pk) < (after_updated_at, after_pk)
            )

        stmt = (
            stmt
            .options(
                selectinload(Item.tags),
                selectinload(Item.applies_to),
                selectinload(Item.external_links),
            )
            .order_by(Item.updated_at.desc(), Item.pk.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _json_path(key: str) -> str:
    return f"$.{json.dumps(key)}"


def _json_value(value: object) -> object:
    if isinstance(value, bool):
        return 1 if value else 0
    return value


def _custom_field_where(field_filter: CustomFieldFilter):
    path = _json_path(field_filter.key)
    value = func.json_extract(Item.custom_fields_json, path)
    value_type = func.json_type(Item.custom_fields_json, path)
    if field_filter.op == "eq":
        return value == _json_value(field_filter.value)
    if field_filter.op == "gt":
        return func.cast(value, Float) > field_filter.value
    if field_filter.op == "gte":
        return func.cast(value, Float) >= field_filter.value
    if field_filter.op == "lt":
        return func.cast(value, Float) < field_filter.value
    if field_filter.op == "lte":
        return func.cast(value, Float) <= field_filter.value
    if field_filter.op == "present":
        return value_type.is_not(None)
    return or_(value_type.is_(None), value == "")
