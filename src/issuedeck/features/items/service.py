"""ItemService — business logic for the items feature.

Owns transaction boundaries. Returns Pydantic DTOs, never ORM objects. Validates
kind/status/branch against ConfigRegistry — all other validation is Pydantic.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from issuedeck.core.config import ConfigRegistry, WebhookEvent
from issuedeck.core.errors import (
    InvalidTransition,
    ItemNotFound,
    ShipRequiresBranchConfig,
)
from issuedeck.features.items.custom_fields import (
    custom_fields_from_json,
    custom_fields_to_json,
    normalize_custom_field_filters,
    normalize_custom_fields,
)
from issuedeck.features.items.models import (
    Item,
    ItemApplyTo,
    ItemEvent,
    ItemExternalLink,
    ItemRelationship,
    ShipRecord,
)
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import (
    BulkUpdateItemsRequest,
    BulkUpdateItemsResponse,
    CreateItemEventRequest,
    CreateItemRequest,
    ExternalLinkInput,
    ExternalLinkOut,
    ItemDetail,
    ItemEventOut,
    ItemListResponse,
    ItemSummary,
    RelationshipOut,
    ShipItemRequest,
    ShipRecordOut,
    UpdateItemRequest,
)


class WebhookEmitter(Protocol):
    def emit(self, event: WebhookEvent, item: ItemSummary) -> None:
        ...


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _preview(body: str, n: int = 200) -> str:
    return (body[:n] + "\u2026") if len(body) > n else body


def _metadata_json(metadata: dict | None) -> str:
    return json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)


def _changed_fields(req: UpdateItemRequest) -> list[str]:
    fields: list[str] = []
    if req.title is not None:
        fields.append("title")
    if req.body is not None or req.append_body is not None:
        fields.append("body")
    if req.status is not None:
        fields.append("status")
    if req.tags is not None:
        fields.append("tags")
    if req.applies_to is not None:
        fields.append("applies_to")
    if req.external_links is not None:
        fields.append("external_links")
    if req.custom_fields is not None:
        fields.append("custom_fields")
    return fields


def _bulk_changed_fields(req: BulkUpdateItemsRequest) -> list[str]:
    fields: list[str] = []
    if req.kind is not None:
        fields.append("kind")
    if req.status is not None:
        fields.append("status")
    if req.tags is not None:
        fields.append("tags")
    if req.applies_to is not None:
        fields.append("applies_to")
    if req.custom_fields is not None:
        fields.append("custom_fields")
    return fields


def _merge_tags(existing: list[str], incoming: list[str], mode: str) -> list[str]:
    if mode == "replace":
        return list(incoming)
    if mode == "remove":
        remove = set(incoming)
        return [tag for tag in existing if tag not in remove]
    result = list(existing)
    for tag in incoming:
        if tag not in result:
            result.append(tag)
    return result


def _link_payloads(links: list[ExternalLinkInput]) -> list[dict[str, str | None]]:
    payloads: list[dict[str, str | None]] = []
    seen_urls: set[str] = set()
    for link in links:
        if link.url in seen_urls:
            continue
        seen_urls.add(link.url)
        payloads.append({
            "link_type": link.link_type,
            "label": link.label,
            "url": link.url,
        })
    return payloads


class ItemService:
    def __init__(
        self,
        repo: ItemRepo,
        registry: ConfigRegistry,
        session: AsyncSession,
        *,
        webhook_dispatcher: WebhookEmitter | None = None,
    ):
        self._repo = repo
        self._registry = registry
        self._s = session
        self._webhook_dispatcher = webhook_dispatcher

    async def create(
        self, project_key: str, req: CreateItemRequest,
    ) -> ItemSummary:
        project_cfg = self._registry.project(project_key)
        kind_cfg = self._registry.validate_kind(project_key, req.kind)

        applies = req.applies_to
        if applies is None:
            applies = [b.key for b in project_cfg.branches]
        for b in applies:
            self._registry.validate_branch(project_key, b)

        status = next(iter(project_cfg.statuses.keys()))
        custom_fields = normalize_custom_fields(project_cfg, req.custom_fields)

        local_id = await self._repo.next_local_id(
            project_key, kind=req.kind,
            prefix=kind_cfg.prefix, digits=project_cfg.id_format.digits,
        )
        item = await self._repo.insert_item(
            project_key=project_key, local_id=local_id,
            kind=req.kind, status=status, title=req.title, body=req.body,
            tags=req.tags, applies_to=applies,
            custom_fields_json=custom_fields_to_json(custom_fields),
            external_links=_link_payloads(req.external_links),
        )
        await self._record_event(
            item,
            event_type="created",
            body=f"Created {local_id}.",
            metadata={"kind": req.kind, "status": status},
        )
        await self._s.commit()
        item = await self._load_eager(project_key, local_id)
        summary = self._to_summary(item)
        self._emit_webhook("item.created", summary)
        return summary

    async def update(
        self, project_key: str, local_id: str, req: UpdateItemRequest,
    ) -> ItemSummary:
        item = await self._load_eager(project_key, local_id)
        if item is None:
            raise ItemNotFound(
                f"item {local_id} not found in project '{project_key}'",
                details={"project_key": project_key, "local_id": local_id},
            )

        if req.status is not None:
            self._registry.validate_status(project_key, req.status)

        body = req.body
        if req.append_body is not None:
            sep = "" if (item.body or "").endswith("\n") else "\n"
            body = f"{item.body}{sep}{req.append_body}" if item.body else req.append_body

        if req.applies_to is not None:
            for b in req.applies_to:
                self._registry.validate_branch(project_key, b)

        custom_fields_json = None
        if req.custom_fields is not None:
            project_cfg = self._registry.project(project_key)
            custom_fields_json = custom_fields_to_json(
                normalize_custom_fields(
                    project_cfg,
                    req.custom_fields,
                    existing=custom_fields_from_json(item.custom_fields_json),
                )
            )

        changed_fields = _changed_fields(req)
        await self._repo.update_item_fields(
            item,
            title=req.title, body=body, status=req.status,
            tags=req.tags, applies_to=req.applies_to,
            custom_fields_json=custom_fields_json,
            external_links=(
                _link_payloads(req.external_links)
                if req.external_links is not None
                else None
            ),
        )
        if changed_fields:
            await self._record_event(
                item,
                event_type="updated",
                body=f"Updated {', '.join(changed_fields)}.",
                metadata={"fields": changed_fields},
            )
        await self._s.commit()
        item = await self._load_eager(project_key, local_id)
        summary = self._to_summary(item)
        if changed_fields:
            self._emit_webhook("item.updated", summary)
        return summary

    async def bulk_update(
        self,
        project_key: str,
        req: BulkUpdateItemsRequest,
    ) -> BulkUpdateItemsResponse:
        project_cfg = self._registry.project(project_key)

        if req.action == "update":
            if req.kind is not None:
                self._registry.validate_kind(project_key, req.kind)
            if req.status is not None:
                status_cfg = self._registry.validate_status(project_key, req.status)
                if status_cfg.requires_ship:
                    raise InvalidTransition(
                        "cannot set a ship-required status via bulk update; use ship",
                        details={"project_key": project_key, "status": req.status},
                    )
            if req.applies_to is not None:
                for branch in req.applies_to:
                    self._registry.validate_branch(project_key, branch)
            if req.custom_fields is not None:
                normalize_custom_field_filters(project_cfg, req.custom_fields)

        include_deleted = req.action == "restore"
        rows = await self._repo.list_by_local_ids(
            project_key,
            req.local_ids,
            include_deleted=include_deleted,
        )
        by_local_id = {item.local_id: item for item in rows}
        missing = [
            local_id for local_id in req.local_ids
            if local_id not in by_local_id
        ]
        if missing:
            raise ItemNotFound(
                f"{len(missing)} item(s) not found in project '{project_key}'",
                details={"project_key": project_key, "local_ids": missing},
            )

        summaries: list[ItemSummary] = []
        if req.action == "delete":
            deleted_at = _iso_now()
            for local_id in req.local_ids:
                item = by_local_id[local_id]
                await self._record_event(
                    item,
                    event_type="deleted",
                    body=(
                        "Deleted item."
                        if not req.reason
                        else f"Deleted item: {req.reason}"
                    ),
                    metadata={"reason": req.reason, "bulk": True} if req.reason else {"bulk": True},
                    created_at=deleted_at,
                )
                await self._repo.soft_delete(item.pk, deleted_at=deleted_at)
            await self._s.commit()
            summaries = await self._load_many_summaries(
                project_key,
                req.local_ids,
                include_deleted=True,
            )
            for summary in summaries:
                self._emit_webhook("item.deleted", summary)
        elif req.action == "restore":
            restored_at = _iso_now()
            for local_id in req.local_ids:
                item = by_local_id[local_id]
                await self._repo.restore(item.pk)
                item.updated_at = restored_at
                await self._record_event(
                    item,
                    event_type="restored",
                    body="Restored item.",
                    metadata={"bulk": True},
                    created_at=restored_at,
                )
            await self._s.commit()
            summaries = await self._load_many_summaries(project_key, req.local_ids)
            for summary in summaries:
                self._emit_webhook("item.restored", summary)
        else:
            changed_fields = _bulk_changed_fields(req)
            for local_id in req.local_ids:
                item = by_local_id[local_id]
                tags = None
                if req.tags is not None:
                    tags = _merge_tags(
                        [tag.tag for tag in item.tags],
                        req.tags,
                        req.tag_mode,
                    )
                custom_fields_json = None
                if req.custom_fields is not None:
                    custom_fields_json = custom_fields_to_json(
                        normalize_custom_fields(
                            project_cfg,
                            req.custom_fields,
                            existing=custom_fields_from_json(item.custom_fields_json),
                        )
                    )
                await self._repo.update_item_fields(
                    item,
                    kind=req.kind,
                    status=req.status,
                    tags=tags,
                    applies_to=req.applies_to,
                    custom_fields_json=custom_fields_json,
                )
                await self._record_event(
                    item,
                    event_type="updated",
                    body=f"Bulk updated {', '.join(changed_fields)}.",
                    metadata={
                        "fields": changed_fields,
                        "bulk": True,
                        "tag_mode": req.tag_mode if req.tags is not None else None,
                    },
                )
            await self._s.commit()
            summaries = await self._load_many_summaries(project_key, req.local_ids)
            for summary in summaries:
                self._emit_webhook("item.updated", summary)

        return BulkUpdateItemsResponse(
            action=req.action,
            requested_count=len(req.local_ids),
            updated_count=len(summaries),
            items=summaries,
        )

    async def ship(
        self, project_key: str, local_id: str, req: ShipItemRequest,
    ) -> ItemSummary:
        project_cfg = self._registry.project(project_key)
        if not project_cfg.branches:
            raise ShipRequiresBranchConfig(
                f"project '{project_key}' has no branches declared; cannot ship",
                details={"project_key": project_key},
            )
        self._registry.validate_branch(project_key, req.branch)
        item = await self._load_eager(project_key, local_id)
        if item is None:
            raise ItemNotFound(
                f"item {local_id} not found in project '{project_key}'",
                details={"project_key": project_key, "local_id": local_id},
            )

        shipped_at = _iso_now()
        await self._repo.upsert_ship_record(
            item_pk=item.pk, branch_key=req.branch, version=req.version,
            shipped_at=shipped_at, commits=req.commits,
        )

        existing_branches = {a.branch_key for a in item.applies_to}
        if req.branch not in existing_branches:
            item.applies_to.append(ItemApplyTo(item_pk=item.pk, branch_key=req.branch))

        item.status = "done"
        item.updated_at = shipped_at
        await self._record_event(
            item,
            event_type="shipped",
            body=f"Shipped to {req.branch} as {req.version}.",
            metadata={
                "branch": req.branch,
                "version": req.version,
                "commits": req.commits,
            },
            created_at=shipped_at,
        )
        await self._s.commit()
        item = await self._load_eager(project_key, local_id)
        summary = self._to_summary(item)
        self._emit_webhook("item.shipped", summary)
        return summary

    async def soft_delete(
        self, project_key: str, local_id: str, *, reason: str = "",
    ) -> None:
        item = await self._load_or_404(project_key, local_id)
        deleted_at = _iso_now()
        await self._record_event(
            item,
            event_type="deleted",
            body="Deleted item." if not reason else f"Deleted item: {reason}",
            metadata={"reason": reason} if reason else {},
            created_at=deleted_at,
        )
        await self._repo.soft_delete(item.pk, deleted_at=deleted_at)
        await self._s.commit()
        item = await self._load_eager(project_key, local_id, include_deleted=True)
        if item is not None:
            self._emit_webhook("item.deleted", self._to_summary(item))

    async def restore(self, project_key: str, local_id: str) -> ItemSummary:
        item = await self._repo.get_by_local_id(
            project_key, local_id, include_deleted=True,
        )
        if item is None:
            raise ItemNotFound(
                f"item {local_id} not found in project '{project_key}'",
                details={"project_key": project_key, "local_id": local_id},
            )
        restored_at = _iso_now()
        await self._repo.restore(item.pk)
        item.updated_at = restored_at
        await self._record_event(
            item,
            event_type="restored",
            body="Restored item.",
            created_at=restored_at,
        )
        await self._s.commit()
        item = await self._load_eager(project_key, local_id, include_deleted=False)
        summary = self._to_summary(item)
        self._emit_webhook("item.restored", summary)
        return summary

    async def add_event(
        self, project_key: str, local_id: str, req: CreateItemEventRequest,
    ) -> ItemEventOut:
        self._registry.project(project_key)
        item = await self._load_or_404(project_key, local_id)
        created_at = _iso_now()
        event = await self._record_event(
            item,
            event_type=req.event_type,
            actor_type=req.actor_type,
            actor_name=req.actor_name,
            body=req.body,
            metadata=req.metadata,
            created_at=created_at,
        )
        item.updated_at = created_at
        await self._s.commit()
        return self._to_event(event)

    async def get(
        self, project_key: str, local_id: str, *, include_deleted: bool = False,
    ) -> ItemDetail:
        item = await self._load_eager(
            project_key, local_id, include_deleted=include_deleted,
        )
        if item is None:
            raise ItemNotFound(
                f"item {local_id} not found in project '{project_key}'",
                details={"project_key": project_key, "local_id": local_id},
            )
        return await self._to_detail(item)

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
        custom_fields: dict[str, object] | None = None,
        since: str | None = None,
        include_deleted: bool = False,
        only_deleted: bool = False,
        limit: int = 50,
        after: str | None = None,
    ) -> ItemListResponse:
        from issuedeck.core.pagination import decode_cursor, encode_cursor

        project_cfg = self._registry.project(project_key)  # 404 if missing
        custom_field_filters = (
            normalize_custom_field_filters(project_cfg, custom_fields)
            if custom_fields
            else None
        )

        after_ts, after_pk = (None, None)
        if after:
            c = decode_cursor(after)
            after_ts, after_pk = c.updated_at, c.pk

        limit = max(1, min(limit, 500))

        rows = await self._repo.list_items(
            project_key,
            kinds=kinds, statuses=statuses, applies_to=applies_to,
            shipped_in_branch=shipped_in_branch,
            shipped_in_version=shipped_in_version, tags=tags,
            custom_fields=custom_field_filters,
            relationship_types=relationship_types, since=since,
            include_deleted=include_deleted, only_deleted=only_deleted,
            limit=limit + 1,
            after_updated_at=after_ts, after_pk=after_pk,
        )
        has_more = len(rows) > limit
        rows = rows[:limit]

        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = encode_cursor(last.updated_at, last.pk)

        return ItemListResponse(
            items=[self._to_summary(i) for i in rows],
            next_cursor=next_cursor,
            limit=limit,
        )

    async def _load_or_404(self, project_key: str, local_id: str) -> Item:
        item = await self._repo.get_by_local_id(project_key, local_id)
        if item is None:
            raise ItemNotFound(
                f"item {local_id} not found in project '{project_key}'",
                details={"project_key": project_key, "local_id": local_id},
            )
        return item

    async def _load_many_summaries(
        self,
        project_key: str,
        local_ids: list[str],
        *,
        include_deleted: bool = False,
    ) -> list[ItemSummary]:
        rows = await self._repo.list_by_local_ids(
            project_key,
            local_ids,
            include_deleted=include_deleted,
        )
        by_local_id = {item.local_id: item for item in rows}
        return [
            self._to_summary(by_local_id[local_id])
            for local_id in local_ids
            if local_id in by_local_id
        ]

    async def _record_event(
        self,
        item: Item,
        *,
        event_type: str,
        body: str,
        actor_type: str = "system",
        actor_name: str = "issuedeck",
        metadata: dict | None = None,
        created_at: str | None = None,
    ) -> ItemEvent:
        return await self._repo.add_event(
            item_pk=item.pk,
            event_type=event_type,
            actor_type=actor_type,
            actor_name=actor_name,
            body=body,
            metadata_json=_metadata_json(metadata),
            created_at=created_at or _iso_now(),
        )

    async def _load_eager(
        self, project_key: str, local_id: str, *, include_deleted: bool = False,
    ) -> Item | None:
        """Load item with all relationships eagerly (no lazy-load in async)."""
        stmt = (
            select(Item)
            .where(Item.project_key == project_key, Item.local_id == local_id)
            .options(
                selectinload(Item.tags),
                selectinload(Item.applies_to),
                selectinload(Item.external_links),
                selectinload(Item.ship_records).selectinload(ShipRecord.commits),
            )
        )
        if not include_deleted:
            stmt = stmt.where(Item.deleted_at.is_(None))
        return (await self._s.execute(stmt)).scalar_one_or_none()

    def _to_summary(self, item: Item) -> ItemSummary:
        return ItemSummary(
            project_key=item.project_key, local_id=item.local_id,
            kind=item.kind, status=item.status, title=item.title,
            body_preview=_preview(item.body or ""),
            tags=[t.tag for t in item.tags],
            applies_to=[a.branch_key for a in item.applies_to],
            custom_fields=custom_fields_from_json(item.custom_fields_json),
            external_links=[self._to_external_link(link) for link in item.external_links],
            created_at=item.created_at, updated_at=item.updated_at,
            deleted_at=item.deleted_at,
        )

    def _emit_webhook(self, event: WebhookEvent, item: ItemSummary) -> None:
        if self._webhook_dispatcher is None:
            return
        self._webhook_dispatcher.emit(event, item)

    async def _to_detail(self, item: Item) -> ItemDetail:
        events = await self._repo.list_events(item.pk)

        ship_out: list[ShipRecordOut] = []
        for sr in item.ship_records:
            ship_out.append(ShipRecordOut(
                branch_key=sr.branch_key, version=sr.version,
                shipped_at=sr.shipped_at, commits=[c.sha for c in sr.commits],
            ))

        rels = (await self._s.execute(
            select(ItemRelationship).where(ItemRelationship.from_item_pk == item.pk)
        )).scalars().all()
        rel_out: list[RelationshipOut] = []
        for r in rels:
            target = (await self._s.execute(
                select(Item).where(Item.pk == r.to_item_pk)
            )).scalar_one_or_none()
            if target is None:
                continue
            rel_out.append(RelationshipOut(
                rel_id=r.id, to_local_id=target.local_id, relation_type=r.relation_type,
            ))

        return ItemDetail(
            project_key=item.project_key, local_id=item.local_id,
            kind=item.kind, status=item.status, title=item.title,
            body=item.body or "",
            tags=[t.tag for t in item.tags],
            applies_to=[a.branch_key for a in item.applies_to],
            custom_fields=custom_fields_from_json(item.custom_fields_json),
            external_links=[self._to_external_link(link) for link in item.external_links],
            created_at=item.created_at, updated_at=item.updated_at,
            deleted_at=item.deleted_at,
            ship_records=ship_out, relationships=rel_out,
            events=[self._to_event(e) for e in events],
        )

    def _to_external_link(self, link: ItemExternalLink) -> ExternalLinkOut:
        return ExternalLinkOut(
            id=link.id,
            link_type=link.link_type,
            label=link.label,
            url=link.url,
            created_at=link.created_at,
        )

    def _to_event(self, event: ItemEvent) -> ItemEventOut:
        try:
            metadata = json.loads(event.metadata_json or "{}")
        except json.JSONDecodeError:
            metadata = {"raw": event.metadata_json}
        if not isinstance(metadata, dict):
            metadata = {"value": metadata}
        return ItemEventOut(
            id=event.id,
            event_type=event.event_type,
            actor_type=event.actor_type,
            actor_name=event.actor_name,
            body=event.body,
            metadata=metadata,
            created_at=event.created_at,
        )
