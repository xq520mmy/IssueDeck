"""Import CSV tracker exports into IssueDeck items."""

from __future__ import annotations

import csv
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from issuedeck.core.config import ConfigRegistry, ProjectConfig
from issuedeck.features.items.custom_fields import (
    custom_fields_to_json,
    normalize_custom_fields,
)
from issuedeck.features.items.external_links import normalize_external_link_payload
from issuedeck.features.items.repo import ItemRepo

_URL_RE = re.compile(r"https?://[^\s<>\]\),;|]+")


@dataclass(frozen=True)
class CsvItemMapping:
    title: tuple[str, ...] = ("title", "summary", "name")
    body: tuple[str, ...] = ("body", "description", "notes", "details")
    kind: tuple[str, ...] = ("kind", "type", "category", "issue_type")
    status: tuple[str, ...] = ("status", "state", "workflow", "workflow_state")
    tags: tuple[str, ...] = ("tags", "labels", "keywords", "label_names")
    applies_to: tuple[str, ...] = ("applies_to", "branch", "branches", "fix_version")
    external_links: tuple[str, ...] = ("external_links", "links", "refs", "references")
    source_id: tuple[str, ...] = ("source_id", "id", "key", "identifier", "issue_key", "number")
    source_url: tuple[str, ...] = ("source_url", "html_url", "web_url", "url")
    custom_fields: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @classmethod
    def from_alias_options(
        cls,
        options: list[str] | None,
        *,
        presets: list[str] | None = None,
    ) -> CsvItemMapping:
        mapping = cls()
        aliases_by_field = {field: list(getattr(mapping, field)) for field in _MAPPABLE_FIELDS}
        custom_fields: dict[str, list[str]] = {
            key: list(aliases)
            for key, aliases in mapping.custom_fields.items()
        }

        for preset in presets or []:
            preset_key = preset.strip().lower()
            try:
                preset_aliases = _MAPPING_PRESETS[preset_key]
            except KeyError as exc:
                expected = ", ".join(sorted(_MAPPING_PRESETS))
                raise ValueError(
                    f"unknown CSV preset '{preset}'; expected one of: {expected}"
                ) from exc
            for target_field, aliases in preset_aliases.items():
                for alias in aliases:
                    if alias not in aliases_by_field[target_field]:
                        aliases_by_field[target_field].append(alias)

        for option in options or []:
            if "=" not in option:
                raise ValueError(f"invalid field alias '{option}'; expected FIELD=alias[,alias...]")
            field, raw_aliases = option.split("=", 1)
            field = field.strip()
            if field == "id":
                field = "source_id"
            custom_field_key = _custom_field_key(field)
            if custom_field_key is not None:
                target_aliases = custom_fields.setdefault(custom_field_key, [])
            elif field in aliases_by_field:
                target_aliases = aliases_by_field[field]
            else:
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
                    "custom.<field_key>",
                ])
                raise ValueError(f"unknown CSV field '{field}'; expected one of: {expected}")
            for alias in raw_aliases.split(","):
                alias = alias.strip()
                if alias and alias not in target_aliases:
                    target_aliases.append(alias)

        return cls(
            **{field: tuple(aliases) for field, aliases in aliases_by_field.items()},
            custom_fields={key: tuple(aliases) for key, aliases in custom_fields.items()},
        )

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
class CsvImportRow:
    title: str
    body: str
    kind: str
    status: str
    tags: list[str]
    applies_to: list[str]
    external_links: list[dict[str, str | None]]
    custom_fields: dict[str, object]
    source_id: str
    source_url: str
    row_number: int


@dataclass
class CsvImportReport:
    rows_found: int = 0
    rows_skipped: int = 0
    items_planned: int = 0
    items_written: int = 0
    status_mapped: int = 0
    external_links: int = 0
    custom_fields: int = 0


def parse_status_map_options(options: list[str] | None) -> dict[str, str]:
    status_map: dict[str, str] = {}
    for option in options or []:
        if "=" not in option:
            raise ValueError(f"invalid status map '{option}'; expected SOURCE=TARGET")
        source, target = option.split("=", 1)
        source = source.strip()
        target = target.strip()
        if not source or not target:
            raise ValueError(f"invalid status map '{option}'; expected SOURCE=TARGET")
        status_map[_normalize_value(source)] = target
    return status_map


def parse_csv_items(
    source: Path,
    *,
    mapping: CsvItemMapping | None = None,
) -> tuple[list[CsvImportRow], CsvImportReport]:
    """Parse a CSV file into raw IssueDeck import rows."""
    if not source.is_file():
        raise ValueError(f"CSV source file not found: {source}")

    mapping = mapping or CsvItemMapping()
    rows: list[CsvImportRow] = []
    report = CsvImportReport()
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV source must include a header row")
        header_index = _header_index(reader.fieldnames)

        for row_number, row in enumerate(reader, start=2):
            if _is_blank_row(row):
                report.rows_skipped += 1
                continue
            report.rows_found += 1
            title = _field(row, header_index, mapping.title)
            if not title:
                accepted = ", ".join(mapping.title)
                raise ValueError(f"row {row_number}: missing required title (accepted: {accepted})")
            body = _field(row, header_index, mapping.body)
            source_id = _field(row, header_index, mapping.source_id)
            source_url = _field(row, header_index, mapping.source_url)
            external_links = _external_links_for_values([
                _field(row, header_index, mapping.external_links),
                source_url,
            ])
            custom_fields = _custom_fields_for_row(row, header_index, mapping.custom_fields)
            rows.append(CsvImportRow(
                title=title,
                body=body,
                kind=_field(row, header_index, mapping.kind),
                status=_field(row, header_index, mapping.status),
                tags=_split_list(_field(row, header_index, mapping.tags)),
                applies_to=_split_list(_field(row, header_index, mapping.applies_to)),
                external_links=external_links,
                custom_fields=custom_fields,
                source_id=source_id,
                source_url=source_url,
                row_number=row_number,
            ))

    report.items_planned = len(rows)
    report.external_links = sum(len(row.external_links) for row in rows)
    report.custom_fields = sum(len(row.custom_fields) for row in rows)
    return rows, report


async def import_csv_items(
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
    mapping: CsvItemMapping | None = None,
    dry_run: bool = False,
) -> CsvImportReport:
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

    rows, report = parse_csv_items(source, mapping=mapping)
    prepared: list[tuple[CsvImportRow, str, str, list[str], dict[str, object]]] = []
    for row in rows:
        row_kind = _resolve_kind(row.kind, project, default_kind=kind, row_number=row.row_number)
        row_status, was_mapped = _resolve_status(
            row.status,
            project,
            default_status=fallback_status,
            terminal_status=terminal_status,
            status_map=normalized_status_map,
            row_number=row.row_number,
        )
        row_branches = _resolve_branches(
            row.applies_to,
            project,
            default_branches=default_branches,
            row_number=row.row_number,
        )
        if was_mapped:
            report.status_mapped += 1
        row_custom_fields = normalize_custom_fields(project, row.custom_fields)
        prepared.append((row, row_kind, row_status, row_branches, row_custom_fields))

    if dry_run:
        return report

    repo = ItemRepo(db)
    for row, row_kind, row_status, row_branches, row_custom_fields in prepared:
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
            tags=_dedupe(["csv", *(tags or []), *row.tags]),
            applies_to=row_branches,
            custom_fields_json=custom_fields_to_json(row_custom_fields),
            external_links=row.external_links,
        )
        report.items_written += 1

    await db.commit()
    return report


def _header_index(fieldnames: list[str]) -> dict[str, str]:
    return {_normalize_header(field): field for field in fieldnames if field is not None}


def _field(
    row: Mapping[str, object],
    header_index: dict[str, str],
    aliases: tuple[str, ...],
) -> str:
    for alias in aliases:
        key = header_index.get(_normalize_header(alias))
        if key is None:
            continue
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _is_blank_row(row: Mapping[str, object]) -> bool:
    for key, value in row.items():
        if key is None:
            continue
        if value is not None and str(value).strip():
            return False
    return True


def _custom_fields_for_row(
    row: Mapping[str, object],
    header_index: dict[str, str],
    custom_field_aliases: dict[str, tuple[str, ...]],
) -> dict[str, object]:
    values: dict[str, object] = {}
    for field_key, aliases in custom_field_aliases.items():
        value = _field(row, header_index, aliases)
        if value:
            values[field_key] = value
    return values


def _split_list(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[\n,;|]+", value)
    return _dedupe([part.strip() for part in parts])


def _external_links_for_values(values: list[str]) -> list[dict[str, str | None]]:
    links: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        candidates = _split_list(value)
        for candidate in candidates:
            urls = _URL_RE.findall(candidate)
            if not urls and candidate.startswith(("http://", "https://")):
                urls = [candidate]
            for url in urls:
                normalized = normalize_external_link_payload({"url": url})
                normalized_url = str(normalized["url"])
                if normalized_url in seen:
                    continue
                seen.add(normalized_url)
                links.append({
                    "link_type": str(normalized["link_type"]),
                    "label": normalized.get("label"),
                    "url": normalized_url,
                })
    return links


def _resolve_kind(
    raw_kind: str,
    project: ProjectConfig,
    *,
    default_kind: str,
    row_number: int,
) -> str:
    if not raw_kind:
        return default_kind
    resolved = _match_key_or_label(raw_kind, {key: cfg.label for key, cfg in project.kinds.items()})
    if resolved is None:
        expected = ", ".join(sorted(project.kinds.keys()))
        raise ValueError(f"row {row_number}: unknown kind '{raw_kind}' (expected: {expected})")
    return resolved


def _resolve_status(
    raw_status: str,
    project: ProjectConfig,
    *,
    default_status: str,
    terminal_status: str,
    status_map: dict[str, str],
    row_number: int,
) -> tuple[str, bool]:
    if not raw_status:
        return default_status, False

    normalized = _normalize_value(raw_status)
    if normalized in status_map:
        return status_map[normalized], status_map[normalized] != raw_status

    resolved = _match_key_or_label(raw_status, {
        key: cfg.label for key, cfg in project.statuses.items()
    })
    if resolved is not None:
        return resolved, _normalize_value(resolved) != normalized

    if normalized in {"open", "opened", "todo", "to_do", "backlog", "new", "proposed"}:
        return default_status, True
    if normalized in {"closed", "done", "resolved", "complete", "completed"}:
        return terminal_status, True
    if normalized in {"in_progress", "inprogress", "started", "doing"}:
        in_progress = _match_key_or_label("in_progress", {
            key: cfg.label for key, cfg in project.statuses.items()
        })
        return in_progress or default_status, True

    expected = ", ".join(sorted(project.statuses.keys()))
    raise ValueError(
        f"row {row_number}: unknown status '{raw_status}' "
        f"(expected: {expected}; or pass --status-map {raw_status}=TARGET)"
    )


def _resolve_branches(
    raw_branches: list[str],
    project: ProjectConfig,
    *,
    default_branches: list[str],
    row_number: int,
) -> list[str]:
    if not raw_branches:
        return default_branches

    labels = {branch.key: branch.label for branch in project.branches}
    resolved: list[str] = []
    for raw_branch in raw_branches:
        branch = _match_key_or_label(raw_branch, labels)
        if branch is None:
            expected = ", ".join(branch.key for branch in project.branches)
            raise ValueError(
                f"row {row_number}: unknown branch '{raw_branch}' (expected: {expected})"
            )
        resolved.append(branch)
    return _dedupe(resolved)


def _match_key_or_label(raw_value: str, labels_by_key: dict[str, str]) -> str | None:
    normalized = _normalize_value(raw_value)
    for key, label in labels_by_key.items():
        if _normalize_value(key) == normalized or _normalize_value(label) == normalized:
            return key
    return None


def _default_statuses(project: ProjectConfig) -> tuple[str, str]:
    open_status = next(
        (key for key, cfg in project.statuses.items() if not cfg.terminal),
        next(iter(project.statuses.keys())),
    )
    terminal_status = next(
        (key for key, cfg in project.statuses.items() if cfg.terminal),
        open_status,
    )
    return open_status, terminal_status


def _target_branches(project: ProjectConfig, applies_to: list[str] | None) -> list[str]:
    if applies_to is not None:
        return applies_to
    return [branch.key for branch in project.branches]


def _row_body(row: CsvImportRow, source: Path) -> str:
    lines: list[str] = []
    if row.body:
        lines.extend([row.body, ""])
    lines.extend([
        "Imported from a CSV tracker export.",
        "",
        f"Source: {source.name}:{row.row_number}",
    ])
    if row.source_id:
        lines.append(f"Source ID: {row.source_id}")
    if row.source_url:
        lines.append(f"Source URL: {row.source_url}")
    return "\n".join(lines)


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _normalize_value(value: str) -> str:
    return _normalize_header(value)


def _custom_field_key(field: str) -> str | None:
    for prefix in ("custom.", "custom_fields."):
        if field.startswith(prefix):
            key = field[len(prefix):].strip()
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", key):
                raise ValueError(
                    f"invalid custom field key '{key}'; expected lowercase letters, "
                    "numbers, - or _"
                )
            return key
    return None


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        clean = value.strip()
        if clean and clean not in result:
            result.append(clean)
    return result
