"""Project export helpers."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from issuedeck.core.config import ConfigRegistry
from issuedeck.features.items.models import (
    ImportBatch,
    Item,
    ItemRelationship,
    ShipRecord,
    WorkSession,
)


@dataclass
class ExportReport:
    items_written: int


@dataclass
class AuditBundleReport:
    bundle_path: Path
    items_written: int
    relationships_written: int
    work_sessions_written: int
    import_batches_written: int


async def export_md_bundle(
    *, session: AsyncSession, registry: ConfigRegistry,
    project_key: str, out_dir: Path,
) -> ExportReport:
    registry.project(project_key)  # raises ProjectNotFound if missing

    items = (await session.execute(
        select(Item)
        .where(Item.project_key == project_key, Item.deleted_at.is_(None))
        .order_by(Item.local_id)
        .options(
            selectinload(Item.tags),
            selectinload(Item.applies_to),
            selectinload(Item.ship_records).selectinload(ShipRecord.commits),
        )
    )).scalars().all()

    items_dir = out_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=True)

    for item in items:
        (items_dir / f"{item.local_id}.md").write_text(
            _render_item_md(item), encoding="utf-8",
        )

    return ExportReport(items_written=len(items))


async def export_audit_bundle(
    *,
    session: AsyncSession,
    registry: ConfigRegistry,
    project_key: str,
    out_path: Path,
) -> AuditBundleReport:
    project = registry.project(project_key)

    items = (await session.execute(
        select(Item)
        .where(Item.project_key == project_key)
        .order_by(Item.local_id)
        .options(
            selectinload(Item.tags),
            selectinload(Item.applies_to),
            selectinload(Item.external_links),
            selectinload(Item.events),
            selectinload(Item.ship_records).selectinload(ShipRecord.commits),
        )
    )).scalars().all()
    item_pk_to_local_id = {item.pk: item.local_id for item in items}
    item_pks = list(item_pk_to_local_id)

    relationships = []
    if item_pks:
        relationships = list((await session.execute(
            select(ItemRelationship)
            .where(
                ItemRelationship.from_item_pk.in_(item_pks),
                ItemRelationship.to_item_pk.in_(item_pks),
            )
            .order_by(ItemRelationship.id)
        )).scalars().all())

    work_sessions = list((await session.execute(
        select(WorkSession)
        .where(WorkSession.project_key == project_key)
        .order_by(WorkSession.updated_at.desc(), WorkSession.id.desc())
        .options(
            selectinload(WorkSession.item),
            selectinload(WorkSession.updates),
        )
    )).scalars().all())

    import_batches = list((await session.execute(
        select(ImportBatch)
        .where(ImportBatch.project_key == project_key)
        .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
    )).scalars().all())

    bundle_path = _audit_bundle_path(out_path, project_key)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "format": "issuedeck.audit_bundle.v1",
        "project_key": project_key,
        "generated_at": datetime.now(UTC).isoformat(),
        "counts": {
            "items": len(items),
            "relationships": len(relationships),
            "work_sessions": len(work_sessions),
            "import_batches": len(import_batches),
        },
        "files": [
            "manifest.json",
            "project.json",
            "items.json",
            "relationships.json",
            "work_sessions.json",
            "import_batches.json",
        ],
    }

    project_toml = registry.server.projects_dir / f"{project_key}.toml"
    if project_toml.exists():
        manifest["files"].append("project.toml")

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        _write_json(bundle, "manifest.json", manifest)
        _write_json(bundle, "project.json", project.model_dump(mode="json"))
        if project_toml.exists():
            bundle.write(project_toml, "project.toml")
        _write_json(bundle, "items.json", [_item_to_dict(item) for item in items])
        _write_json(
            bundle,
            "relationships.json",
            [
                _relationship_to_dict(relationship, item_pk_to_local_id)
                for relationship in relationships
            ],
        )
        _write_json(
            bundle,
            "work_sessions.json",
            [_work_session_to_dict(session) for session in work_sessions],
        )
        _write_json(
            bundle,
            "import_batches.json",
            [_import_batch_to_dict(batch) for batch in import_batches],
        )

    return AuditBundleReport(
        bundle_path=bundle_path,
        items_written=len(items),
        relationships_written=len(relationships),
        work_sessions_written=len(work_sessions),
        import_batches_written=len(import_batches),
    )


def _render_item_md(item: Item) -> str:
    lines: list[str] = ["---"]
    lines.append(f"id: {item.local_id}")
    lines.append(f"kind: {item.kind}")
    lines.append(f"status: {item.status}")
    lines.append(f"title: {_yaml_quote(item.title)}")
    if item.tags:
        lines.append("tags:")
        for t in item.tags:
            lines.append(f"  - {t.tag}")
    if item.applies_to:
        applies = ", ".join(a.branch_key for a in item.applies_to)
        lines.append(f"applies_to: [{applies}]")
    for sr in item.ship_records:
        lines.append(f"shipped_in_{sr.branch_key}: {sr.version}")
        if sr.commits:
            lines.append(f"commits_{sr.branch_key}:")
            for c in sr.commits:
                lines.append(f"  - {c.sha}")
    lines.append(f"created_at: {item.created_at}")
    lines.append(f"updated_at: {item.updated_at}")
    lines.append("---")
    lines.append("")
    lines.append(item.body or "")
    return "\n".join(lines) + "\n"


def _yaml_quote(s: str) -> str:
    if any(c in s for c in ":#\"'\n"):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _audit_bundle_path(out_path: Path, project_key: str) -> Path:
    if out_path.suffix.lower() == ".zip":
        return out_path
    return out_path / f"{project_key}-audit-bundle.zip"


def _write_json(bundle: zipfile.ZipFile, name: str, payload: Any) -> None:
    bundle.writestr(
        name,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _item_to_dict(item: Item) -> dict[str, Any]:
    return {
        "local_id": item.local_id,
        "project_key": item.project_key,
        "kind": item.kind,
        "status": item.status,
        "title": item.title,
        "body": item.body,
        "tags": sorted(tag.tag for tag in item.tags),
        "applies_to": sorted(branch.branch_key for branch in item.applies_to),
        "external_links": [
            {
                "id": link.id,
                "link_type": link.link_type,
                "label": link.label,
                "url": link.url,
                "created_at": link.created_at,
            }
            for link in item.external_links
        ],
        "ship_records": [
            {
                "branch_key": record.branch_key,
                "version": record.version,
                "shipped_at": record.shipped_at,
                "commits": [commit.sha for commit in record.commits],
            }
            for record in item.ship_records
        ],
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "actor_type": event.actor_type,
                "actor_name": event.actor_name,
                "body": event.body,
                "metadata": _metadata(event.metadata_json),
                "created_at": event.created_at,
            }
            for event in sorted(item.events, key=lambda event: (event.created_at, event.id))
        ],
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "deleted_at": item.deleted_at,
    }


def _relationship_to_dict(
    relationship: ItemRelationship,
    item_pk_to_local_id: dict[int, str],
) -> dict[str, Any]:
    return {
        "id": relationship.id,
        "from_local_id": item_pk_to_local_id[relationship.from_item_pk],
        "to_local_id": item_pk_to_local_id[relationship.to_item_pk],
        "relation_type": relationship.relation_type,
        "created_at": relationship.created_at,
    }


def _work_session_to_dict(session: WorkSession) -> dict[str, Any]:
    return {
        "id": session.id,
        "project_key": session.project_key,
        "local_id": session.item.local_id if session.item else None,
        "agent_name": session.agent_name,
        "status": session.status,
        "goal": session.goal,
        "summary": session.summary,
        "branch": session.branch,
        "started_at": session.started_at,
        "updated_at": session.updated_at,
        "ended_at": session.ended_at,
        "metadata": _metadata(session.metadata_json),
        "updates": [
            {
                "id": update.id,
                "update_type": update.update_type,
                "message": update.message,
                "metadata": _metadata(update.metadata_json),
                "created_at": update.created_at,
            }
            for update in sorted(
                session.updates,
                key=lambda update: (update.created_at, update.id),
            )
        ],
    }


def _import_batch_to_dict(batch: ImportBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "project_key": batch.project_key,
        "batch_tag": batch.batch_tag,
        "source_type": batch.source_type,
        "source_name": batch.source_name,
        "items_planned": batch.items_planned,
        "items_written": batch.items_written,
        "skipped_count": batch.skipped_count,
        "status_mapped": batch.status_mapped,
        "external_links": batch.external_links,
        "created_at": batch.created_at,
        "metadata": _metadata(batch.metadata_json),
    }


def _metadata(raw: str) -> Any:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"raw": raw}
