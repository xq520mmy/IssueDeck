"""One-shot migration tool: frontmatter markdown items -> issuedeck SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import frontmatter
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from issuedeck.core.config import ConfigRegistry
from issuedeck.features.items.models import (
    Item,
    ItemApplyTo,
    ItemTag,
    ShipCommit,
    ShipRecord,
)


class MigrationError(Exception):
    pass


@dataclass
class ShipRow:
    branch_key: str
    version: str
    commits: list[str]


@dataclass
class MigrationRow:
    local_id: str
    kind: str
    status: str
    title: str
    body: str
    tags: list[str]
    applies_to: list[str]
    ship_records: list[ShipRow]
    created_at: str
    updated_at: str
    deleted_at: str | None = None


@dataclass
class MigrationReport:
    items_planned: int = 0
    items_written: int = 0
    ship_records: int = 0
    ship_commits: int = 0
    tags: int = 0
    applies_to: int = 0


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def map_frontmatter_to_row(fm: frontmatter.Post, *, is_archived: bool) -> MigrationRow:
    """Pure function: parse item frontmatter into a migration row."""
    d = fm.metadata

    ship: list[ShipRow] = []
    for branch, ver_key, commits_key in (
        ("v3", "shipped_in_v3", "commits_v3"),
        ("v2", "shipped_in_v2", "commits_v2"),
    ):
        version = d.get(ver_key)
        if version:
            ship.append(ShipRow(
                branch_key=branch, version=version,
                commits=list(d.get(commits_key, []) or []),
            ))

    deleted_at = None
    if is_archived:
        deleted_at = d.get("deleted_at") or _iso_now()

    return MigrationRow(
        local_id=d["id"],
        kind=d["kind"],
        status=d["status"],
        title=d["title"],
        body=fm.content or "",
        tags=list(d.get("tags") or []),
        applies_to=list(d.get("applies_to") or []),
        ship_records=ship,
        created_at=d.get("created_at") or _iso_now(),
        updated_at=d.get("updated_at") or _iso_now(),
        deleted_at=deleted_at,
    )


async def migrate_frontmatter_bundle(
    source_dir: Path,
    project_key: str,
    registry: ConfigRegistry,
    db: AsyncSession,
    *,
    dry_run: bool = False,
    force_reset: bool = False,
) -> MigrationReport:
    project_cfg = registry.project(project_key)

    known_kinds = set(project_cfg.kinds.keys())
    known_statuses = set(project_cfg.statuses.keys())
    known_branches = {b.key for b in project_cfg.branches}

    items_dir = source_dir / "items"
    if not items_dir.exists():
        raise MigrationError(f"source items dir not found: {items_dir}")

    active_files = sorted(items_dir.glob("*.md"))
    archived_dir = items_dir / ".archive"
    archived_files = sorted(archived_dir.glob("*.md")) if archived_dir.exists() else []

    parsed: list[MigrationRow] = []
    errors: list[str] = []
    for f, is_archived in [(x, False) for x in active_files] + [(x, True) for x in archived_files]:
        try:
            fm = frontmatter.load(f)
            row = map_frontmatter_to_row(fm, is_archived=is_archived)
            if row.kind not in known_kinds:
                errors.append(f"{f.name}: unknown kind '{row.kind}'")
            if row.status not in known_statuses:
                errors.append(f"{f.name}: unknown status '{row.status}'")
            for b in row.applies_to:
                if b not in known_branches:
                    errors.append(f"{f.name}: unknown branch '{b}' in applies_to")
            for sr in row.ship_records:
                if sr.branch_key not in known_branches:
                    errors.append(f"{f.name}: unknown ship branch '{sr.branch_key}'")
            parsed.append(row)
        except Exception as e:
            errors.append(f"{f.name}: {e}")

    if errors:
        raise MigrationError(
            "Validation failed; no rows written:\n  - " + "\n  - ".join(errors)
        )

    seen: set[str] = set()
    for row in parsed:
        if row.local_id in seen:
            raise MigrationError(f"duplicate local_id in source: {row.local_id}")
        seen.add(row.local_id)

    existing = (await db.execute(
        select(func.count(Item.pk)).where(Item.project_key == project_key)
    )).scalar_one()
    if existing and not force_reset:
        raise MigrationError(
            f"project '{project_key}' already has {existing} rows; "
            f"pass force_reset=True to wipe"
        )

    report = MigrationReport(
        items_planned=len(parsed),
        tags=sum(len(r.tags) for r in parsed),
        applies_to=sum(len(r.applies_to) for r in parsed),
        ship_records=sum(len(r.ship_records) for r in parsed),
        ship_commits=sum(sum(len(s.commits) for s in r.ship_records) for r in parsed),
    )

    if dry_run:
        return report

    if force_reset and existing:
        await db.execute(delete(Item).where(Item.project_key == project_key))
        await db.flush()

    for row in parsed:
        item = Item(
            project_key=project_key, local_id=row.local_id,
            kind=row.kind, status=row.status, title=row.title, body=row.body,
            created_at=row.created_at, updated_at=row.updated_at,
            deleted_at=row.deleted_at,
        )
        db.add(item)
        await db.flush()

        for t in row.tags:
            db.add(ItemTag(item_pk=item.pk, tag=t))
        for b in row.applies_to:
            db.add(ItemApplyTo(item_pk=item.pk, branch_key=b))
        for sr in row.ship_records:
            sr_obj = ShipRecord(
                item_pk=item.pk, branch_key=sr.branch_key,
                version=sr.version, shipped_at=row.updated_at,
            )
            db.add(sr_obj)
            await db.flush()
            for i, sha in enumerate(sr.commits):
                db.add(ShipCommit(
                    ship_record_id=sr_obj.id, sha=sha, position=i,
                ))

    await db.commit()
    report.items_written = len(parsed)

    actual = (await db.execute(
        select(func.count(Item.pk)).where(Item.project_key == project_key)
    )).scalar_one()
    if actual != len(parsed):
        raise MigrationError(
            f"post-write check failed: expected {len(parsed)}, found {actual}"
        )

    return report
