"""One-shot migration tool: frontmatter markdown items -> issuedeck SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import frontmatter
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from issuedeck.core.config import ConfigRegistry
from issuedeck.features.items.external_links import normalize_external_link_payload
from issuedeck.features.items.models import (
    Item,
    ItemApplyTo,
    ItemExternalLink,
    ItemTag,
    ShipCommit,
    ShipRecord,
)


class MigrationError(Exception):
    pass


@dataclass(frozen=True)
class FrontmatterMapping:
    local_id: tuple[str, ...] = ("id",)
    kind: tuple[str, ...] = ("kind", "type")
    status: tuple[str, ...] = ("status", "state")
    title: tuple[str, ...] = ("title",)
    tags: tuple[str, ...] = ("tags", "labels")
    applies_to: tuple[str, ...] = ("applies_to",)
    external_links: tuple[str, ...] = ("external_links",)

    @classmethod
    def from_alias_options(
        cls,
        options: list[str] | None,
        *,
        presets: list[str] | None = None,
    ) -> FrontmatterMapping:
        mapping = cls()

        aliases_by_field = {field: list(getattr(mapping, field)) for field in _MAPPABLE_FIELDS}
        for preset in presets or []:
            preset_key = preset.strip().lower()
            try:
                preset_aliases = _MAPPING_PRESETS[preset_key]
            except KeyError as exc:
                expected = ", ".join(sorted(_MAPPING_PRESETS))
                raise ValueError(
                    f"unknown frontmatter preset '{preset}'; expected one of: {expected}"
                ) from exc
            for field, aliases in preset_aliases.items():
                for alias in aliases:
                    if alias not in aliases_by_field[field]:
                        aliases_by_field[field].append(alias)

        for option in options or []:
            if "=" not in option:
                raise ValueError(
                    f"invalid field alias '{option}'; expected FIELD=alias[,alias...]"
                )
            field, raw_aliases = option.split("=", 1)
            field = field.strip()
            if field == "id":
                field = "local_id"
            if field not in aliases_by_field:
                expected = ", ".join([
                    "id", "kind", "status", "title", "tags",
                    "applies_to", "external_links",
                ])
                raise ValueError(
                    f"unknown frontmatter field '{field}'; expected one of: {expected}"
                )
            for alias in raw_aliases.split(","):
                alias = alias.strip()
                if alias and alias not in aliases_by_field[field]:
                    aliases_by_field[field].append(alias)

        return cls(**{field: tuple(aliases) for field, aliases in aliases_by_field.items()})

    @classmethod
    def available_presets(cls) -> tuple[str, ...]:
        return tuple(sorted(_MAPPING_PRESETS))


_MAPPABLE_FIELDS = (
    "local_id",
    "kind",
    "status",
    "title",
    "tags",
    "applies_to",
    "external_links",
)
_MAPPING_PRESETS: dict[str, dict[str, tuple[str, ...]]] = {
    "github": {
        "local_id": ("number", "issue_number"),
        "status": ("state",),
        "tags": ("labels",),
        "external_links": ("html_url", "url"),
    },
    "linear": {
        "local_id": ("identifier", "issue_id"),
        "status": ("workflow_state",),
        "tags": ("label_names",),
        "applies_to": ("branch", "branches"),
        "external_links": ("url", "links", "attachments"),
    },
    "generic": {
        "local_id": ("key", "local_id"),
        "kind": ("category",),
        "status": ("workflow",),
        "tags": ("keywords",),
        "applies_to": ("branch", "branches"),
        "external_links": ("links", "refs", "references"),
    },
}
_MISSING = object()


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
    external_links: list[dict[str, str | None]]
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
    external_links: int = 0


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def map_frontmatter_to_row(
    fm: frontmatter.Post,
    *,
    is_archived: bool,
    mapping: FrontmatterMapping | None = None,
) -> MigrationRow:
    """Pure function: parse item frontmatter into a migration row."""
    d = fm.metadata
    mapping = mapping or FrontmatterMapping()

    ship: list[ShipRow] = []
    for branch, ver_key, commits_key in (
        ("v3", "shipped_in_v3", "commits_v3"),
        ("v2", "shipped_in_v2", "commits_v2"),
    ):
        version = d.get(ver_key)
        if version:
            ship.append(ShipRow(
                branch_key=branch, version=str(version),
                commits=_normalize_string_list(d.get(commits_key)),
            ))

    deleted_at = None
    if is_archived:
        deleted_at = d.get("deleted_at") or _iso_now()

    return MigrationRow(
        local_id=str(_required_field(d, mapping.local_id, "id")),
        kind=str(_required_field(d, mapping.kind, "kind")),
        status=str(_required_field(d, mapping.status, "status")),
        title=str(_required_field(d, mapping.title, "title")),
        body=fm.content or "",
        tags=_normalize_string_list(_optional_field(d, mapping.tags)),
        applies_to=_normalize_string_list(_optional_field(d, mapping.applies_to)),
        external_links=_normalize_external_links(_optional_field(d, mapping.external_links)),
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
    mapping: FrontmatterMapping | None = None,
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
            row = map_frontmatter_to_row(
                fm,
                is_archived=is_archived,
                mapping=mapping,
            )
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
        external_links=sum(len(r.external_links) for r in parsed),
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
        for link in row.external_links:
            db.add(ItemExternalLink(
                item_pk=item.pk,
                link_type=str(link["link_type"]),
                label=link.get("label"),
                url=str(link["url"]),
                created_at=row.created_at,
            ))
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


def _normalize_external_links(value: object) -> list[dict[str, str | None]]:
    if value is _MISSING or value is None:
        return []

    raw_values: list[object]
    if isinstance(value, str):
        raw_values = [line.strip() for line in value.splitlines() if line.strip()]
        if len(raw_values) == 1 and "," in raw_values[0]:
            raw_values = [part.strip() for part in raw_values[0].split(",") if part.strip()]
    elif isinstance(value, list | tuple | set):
        raw_values = list(value)
    else:
        raw_values = [value]

    normalized: list[dict[str, str | None]] = []
    seen_urls: set[str] = set()
    for raw in raw_values:
        payload = _external_link_payload(raw)
        if payload is None:
            continue
        link = normalize_external_link_payload(payload)
        url = str(link["url"])
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        normalized.append({
            "link_type": str(link["link_type"]),
            "label": link.get("label"),
            "url": url,
        })
    return normalized


def _external_link_payload(raw: object) -> dict[str, object] | None:
    if isinstance(raw, str):
        return {"url": raw.strip()}
    if isinstance(raw, dict):
        payload = dict(raw)
        url = payload.get("url") or payload.get("href") or payload.get("html_url")
        if url is None:
            return None
        payload["url"] = url
        return payload
    return {"url": str(raw).strip()}


def _optional_field(metadata: dict, aliases: tuple[str, ...]) -> object:
    for alias in aliases:
        if alias not in metadata:
            continue
        value = metadata[alias]
        if value is not None and value != "":
            return value
    return _MISSING


def _required_field(metadata: dict, aliases: tuple[str, ...], canonical: str) -> object:
    value = _optional_field(metadata, aliases)
    if value is _MISSING or value == "":
        accepted = ", ".join(aliases)
        raise KeyError(f"missing required frontmatter field '{canonical}' (accepted: {accepted})")
    return value


def _normalize_string_list(value: object) -> list[str]:
    if value is _MISSING or value is None:
        return []

    if isinstance(value, str):
        raw_values: list[object] = value.split(",") if "," in value else [value]
    elif isinstance(value, list | tuple | set):
        raw_values = list(value)
    else:
        raw_values = [value]

    normalized: list[str] = []
    for raw in raw_values:
        if isinstance(raw, dict):
            raw = raw.get("name") or raw.get("label") or raw.get("value")
        if raw is None:
            continue
        text = str(raw).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized
