"""Import JSON tracker exports into IssueDeck items."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from issuedeck.core.config import ConfigRegistry
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.migrate.csv_items import (
    _dedupe,
    _default_statuses,
    _external_links_for_values,
    _normalize_header,
    _normalize_value,
    _resolve_branches,
    _resolve_kind,
    _resolve_status,
    _split_list,
    _target_branches,
)


@dataclass(frozen=True)
class JsonItemMapping:
    title: tuple[str, ...] = ("title", "summary", "name")
    body: tuple[str, ...] = ("body", "description", "notes", "details")
    kind: tuple[str, ...] = ("kind", "type", "category", "issue_type")
    status: tuple[str, ...] = ("status", "state", "workflow", "workflow_state")
    tags: tuple[str, ...] = ("tags", "labels", "keywords", "label_names")
    applies_to: tuple[str, ...] = ("applies_to", "branch", "branches", "fix_version")
    external_links: tuple[str, ...] = ("external_links", "links", "refs", "references")
    source_id: tuple[str, ...] = ("source_id", "id", "key", "identifier", "issue_key", "number")
    source_url: tuple[str, ...] = ("source_url", "html_url", "web_url", "url")

    @classmethod
    def from_alias_options(
        cls,
        options: list[str] | None,
        *,
        presets: list[str] | None = None,
    ) -> JsonItemMapping:
        mapping = cls()
        aliases_by_field = {field: list(getattr(mapping, field)) for field in _MAPPABLE_FIELDS}

        for preset in presets or []:
            preset_key = preset.strip().lower()
            try:
                preset_aliases = _MAPPING_PRESETS[preset_key]
            except KeyError as exc:
                expected = ", ".join(sorted(_MAPPING_PRESETS))
                raise ValueError(
                    f"unknown JSON preset '{preset}'; expected one of: {expected}"
                ) from exc
            for field, aliases in preset_aliases.items():
                for alias in aliases:
                    if alias not in aliases_by_field[field]:
                        aliases_by_field[field].append(alias)

        for option in options or []:
            if "=" not in option:
                raise ValueError(f"invalid field alias '{option}'; expected FIELD=alias[,alias...]")
            field, raw_aliases = option.split("=", 1)
            field = field.strip()
            if field == "id":
                field = "source_id"
            if field not in aliases_by_field:
                expected = ", ".join([
                    "title",
                    "body",
                    "kind",
                    "status",
                    "tags",
                    "applies_to",
                    "external_links",
                    "source_id",
                    "source_url",
                ])
                raise ValueError(f"unknown JSON field '{field}'; expected one of: {expected}")
            for alias in raw_aliases.split(","):
                alias = alias.strip()
                if alias and alias not in aliases_by_field[field]:
                    aliases_by_field[field].append(alias)

        return cls(**{field: tuple(aliases) for field, aliases in aliases_by_field.items()})

    @classmethod
    def available_presets(cls) -> tuple[str, ...]:
        return tuple(sorted(_MAPPING_PRESETS))


_MAPPABLE_FIELDS = (
    "title",
    "body",
    "kind",
    "status",
    "tags",
    "applies_to",
    "external_links",
    "source_id",
    "source_url",
)
_MAPPING_PRESETS: dict[str, dict[str, tuple[str, ...]]] = {
    "generic": {
        "title": ("task", "issue", "subject"),
        "body": ("comment", "comments", "content"),
        "status": ("stage",),
        "applies_to": ("target_branch",),
    },
    "github": {
        "title": ("title",),
        "body": ("body",),
        "status": ("state",),
        "tags": ("labels",),
        "source_id": ("number",),
        "source_url": ("html_url", "url"),
        "external_links": ("html_url", "url"),
    },
    "jira": {
        "title": ("summary",),
        "body": ("description",),
        "kind": ("issue_type", "issuetype", "issue type"),
        "status": ("status",),
        "tags": ("labels", "components"),
        "applies_to": ("fix_versions", "fix version/s", "fix_version"),
        "source_id": ("key", "issue_key", "issue key"),
        "source_url": ("url", "self"),
        "external_links": ("url", "self"),
    },
    "linear": {
        "title": ("title",),
        "body": ("description",),
        "kind": ("type",),
        "status": ("workflow_state", "state"),
        "tags": ("label_names", "labels"),
        "applies_to": ("branch", "branches"),
        "source_id": ("identifier", "issue_id"),
        "source_url": ("url",),
        "external_links": ("url",),
    },
}


@dataclass(frozen=True)
class JsonImportRow:
    title: str
    body: str
    kind: str
    status: str
    tags: list[str]
    applies_to: list[str]
    external_links: list[dict[str, str | None]]
    source_id: str
    source_url: str
    object_number: int


@dataclass
class JsonImportReport:
    objects_found: int = 0
    objects_skipped: int = 0
    items_planned: int = 0
    items_written: int = 0
    status_mapped: int = 0
    external_links: int = 0


def parse_json_items(
    source: Path,
    *,
    mapping: JsonItemMapping | None = None,
) -> tuple[list[JsonImportRow], JsonImportReport]:
    """Parse a JSON export into raw IssueDeck import rows."""
    if not source.is_file():
        raise ValueError(f"JSON source file not found: {source}")

    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON source: {exc}") from exc

    objects = _extract_objects(payload)
    mapping = mapping or JsonItemMapping()
    rows: list[JsonImportRow] = []
    report = JsonImportReport()
    for object_number, obj in enumerate(objects, start=1):
        if not _has_content(obj):
            report.objects_skipped += 1
            continue
        report.objects_found += 1
        title = _field_text(obj, mapping.title)
        if not title:
            accepted = ", ".join(mapping.title)
            raise ValueError(
                f"object {object_number}: missing required title (accepted: {accepted})"
            )
        source_url = _field_text(obj, mapping.source_url)
        external_links = _external_links_for_values([
            *_field_values(obj, mapping.external_links),
            source_url,
        ])
        rows.append(JsonImportRow(
            title=title,
            body=_field_text(obj, mapping.body),
            kind=_field_text(obj, mapping.kind),
            status=_field_text(obj, mapping.status),
            tags=_field_list(obj, mapping.tags),
            applies_to=_field_list(obj, mapping.applies_to),
            external_links=external_links,
            source_id=_field_text(obj, mapping.source_id),
            source_url=source_url,
            object_number=object_number,
        ))

    report.items_planned = len(rows)
    report.external_links = sum(len(row.external_links) for row in rows)
    return rows, report


async def import_json_items(
    source: Path,
    project_key: str,
    registry: ConfigRegistry,
    db: AsyncSession,
    *,
    kind: str,
    default_status: str | None = None,
    tags: list[str] | None = None,
    applies_to: list[str] | None = None,
    status_map: dict[str, str] | None = None,
    mapping: JsonItemMapping | None = None,
    dry_run: bool = False,
) -> JsonImportReport:
    project = registry.project(project_key)
    registry.validate_kind(project_key, kind)
    open_status, terminal_status = _default_statuses(project)
    fallback_status = default_status or open_status
    registry.validate_status(project_key, fallback_status)

    default_branches = _target_branches(project, applies_to)
    for branch in default_branches:
        registry.validate_branch(project_key, branch)

    raw_status_map = status_map or {}
    normalized_status_map = {
        _normalize_value(source): target for source, target in raw_status_map.items()
    }
    for target in normalized_status_map.values():
        registry.validate_status(project_key, target)

    rows, report = parse_json_items(source, mapping=mapping)
    prepared: list[tuple[JsonImportRow, str, str, list[str]]] = []
    for row in rows:
        row_kind = _resolve_kind(row.kind, project, default_kind=kind, row_number=row.object_number)
        row_status, was_mapped = _resolve_status(
            row.status,
            project,
            default_status=fallback_status,
            terminal_status=terminal_status,
            status_map=normalized_status_map,
            row_number=row.object_number,
        )
        row_branches = _resolve_branches(
            row.applies_to,
            project,
            default_branches=default_branches,
            row_number=row.object_number,
        )
        if was_mapped:
            report.status_mapped += 1
        prepared.append((row, row_kind, row_status, row_branches))

    if dry_run:
        return report

    repo = ItemRepo(db)
    for row, row_kind, row_status, row_branches in prepared:
        kind_cfg = registry.validate_kind(project_key, row_kind)
        local_id = await repo.next_local_id(
            project_key,
            kind=row_kind,
            prefix=kind_cfg.prefix,
            digits=project.id_format.digits,
        )
        await repo.insert_item(
            project_key=project_key,
            local_id=local_id,
            kind=row_kind,
            status=row_status,
            title=row.title,
            body=_row_body(row, source),
            tags=_dedupe(["json", *(tags or []), *row.tags]),
            applies_to=row_branches,
            external_links=row.external_links,
        )
        report.items_written += 1

    await db.commit()
    return report


def _extract_objects(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return _dicts_from_list(payload)
    if isinstance(payload, dict):
        for key in ("items", "issues", "data", "records", "tasks"):
            value = payload.get(key)
            if isinstance(value, list):
                return _dicts_from_list(value)
        return [dict(payload)]
    raise ValueError("JSON source must be an object, an array, or an object containing items")


def _dicts_from_list(values: list[object]) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"array element {index} must be a JSON object")
        objects.append(dict(value))
    return objects


def _has_content(obj: dict[str, Any]) -> bool:
    return any(value not in (None, "", [], {}) for value in obj.values())


def _field_text(obj: dict[str, Any], aliases: tuple[str, ...]) -> str:
    value = _field_value(obj, aliases)
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, int | float | bool):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _field_list(obj: dict[str, Any], aliases: tuple[str, ...]) -> list[str]:
    return _dedupe(_field_values(obj, aliases))


def _field_values(obj: dict[str, Any], aliases: tuple[str, ...]) -> list[str]:
    value = _field_value(obj, aliases)
    if value is None:
        return []
    if isinstance(value, str):
        return _split_list(value)
    if isinstance(value, int | float | bool):
        return [str(value)]
    if isinstance(value, list | tuple | set):
        values: list[str] = []
        for item in value:
            values.extend(_json_value_strings(item))
        return _dedupe(values)
    return _json_value_strings(value)


def _field_value(obj: dict[str, Any], aliases: tuple[str, ...]) -> object | None:
    index = {_normalize_header(key): key for key in obj}
    for alias in aliases:
        key = index.get(_normalize_header(alias))
        if key is not None:
            return obj.get(key)
    return None


def _json_value_strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_list(value)
    if isinstance(value, int | float | bool):
        return [str(value)]
    if isinstance(value, dict):
        for key in ("name", "label", "value", "title", "key", "url", "html_url", "web_url"):
            raw = value.get(key)
            if raw is not None and raw != "":
                return _json_value_strings(raw)
        return []
    return [str(value)]


def _row_body(row: JsonImportRow, source: Path) -> str:
    lines: list[str] = []
    if row.body:
        lines.extend([row.body, ""])
    lines.extend([
        "Imported from a JSON tracker export.",
        "",
        f"Source: {source.name}#{row.object_number}",
    ])
    if row.source_id:
        lines.append(f"Source ID: {row.source_id}")
    if row.source_url:
        lines.append(f"Source URL: {row.source_url}")
    return "\n".join(lines)
