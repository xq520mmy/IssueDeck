"""Project-scoped saved dashboard filters stored in the local data directory."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

FILTER_MULTI_FIELDS = ("kind", "status", "tag", "applies_to", "relation_type")
FILTER_BOOL_FIELDS = ("include_deleted",)
FILTER_SCALAR_FIELDS = ("view",)
MAX_FILTERS_PER_PROJECT = 30


@dataclass(frozen=True)
class SavedDashboardFilter:
    id: str
    name: str
    params: dict[str, object]


def list_saved_dashboard_filters(
    data_dir: Path, project_key: str,
) -> list[SavedDashboardFilter]:
    store = _read_store(_store_path(data_dir))
    raw_filters = store.get("projects", {}).get(project_key, [])
    filters: list[SavedDashboardFilter] = []
    for raw in raw_filters:
        if not isinstance(raw, dict):
            continue
        filter_id = raw.get("id")
        name = raw.get("name")
        params = raw.get("params")
        if isinstance(filter_id, str) and isinstance(name, str) and isinstance(params, dict):
            filters.append(SavedDashboardFilter(
                id=filter_id,
                name=name,
                params=normalize_filter_params(params),
            ))
    return filters


def get_saved_dashboard_filter(
    data_dir: Path, project_key: str, filter_id: str,
) -> SavedDashboardFilter | None:
    for saved_filter in list_saved_dashboard_filters(data_dir, project_key):
        if saved_filter.id == filter_id:
            return saved_filter
    return None


def save_dashboard_filter(
    data_dir: Path,
    project_key: str,
    name: str,
    params: dict[str, object],
) -> SavedDashboardFilter:
    clean_name = " ".join(name.split()).strip()
    if not clean_name:
        raise ValueError("saved filter name is required")

    store_path = _store_path(data_dir)
    store = _read_store(store_path)
    projects = store.setdefault("projects", {})
    project_filters = projects.setdefault(project_key, [])

    filter_id = _unique_filter_id(project_filters, _slugify(clean_name))
    saved = {
        "id": filter_id,
        "name": clean_name[:80],
        "params": normalize_filter_params(params),
    }

    project_filters = [f for f in project_filters if f.get("id") != filter_id]
    project_filters.insert(0, saved)
    projects[project_key] = project_filters[:MAX_FILTERS_PER_PROJECT]

    store_path.parent.mkdir(parents=True, exist_ok=True)
    _write_store(store_path, store)
    return SavedDashboardFilter(
        id=saved["id"],
        name=saved["name"],
        params=saved["params"],
    )


def delete_dashboard_filter(data_dir: Path, project_key: str, filter_id: str) -> bool:
    store_path = _store_path(data_dir)
    store = _read_store(store_path)
    projects = store.setdefault("projects", {})
    raw_filters = projects.get(project_key)
    if not isinstance(raw_filters, list):
        return False

    kept_filters = [
        raw for raw in raw_filters
        if not (isinstance(raw, dict) and raw.get("id") == filter_id)
    ]
    if len(kept_filters) == len(raw_filters):
        return False

    projects[project_key] = kept_filters[:MAX_FILTERS_PER_PROJECT]
    store_path.parent.mkdir(parents=True, exist_ok=True)
    _write_store(store_path, store)
    return True


def normalize_filter_params(params: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}

    view = params.get("view")
    if isinstance(view, str) and view:
        normalized["view"] = view

    for field in FILTER_MULTI_FIELDS:
        values = params.get(field)
        clean_values = _normalize_list(values)
        if clean_values:
            normalized[field] = clean_values

    include_deleted = params.get("include_deleted")
    if include_deleted in (True, "true", "True", "1", "on"):
        normalized["include_deleted"] = True

    custom_fields = params.get("custom_fields")
    if isinstance(custom_fields, dict):
        clean_custom_fields: dict[str, str | bool | int | float] = {}
        for key, value in custom_fields.items():
            if not isinstance(key, str):
                continue
            clean_key = key.strip()
            if not clean_key:
                continue
            if isinstance(value, bool | int | float):
                clean_custom_fields[clean_key] = value
                continue
            if isinstance(value, str):
                clean_value = value.strip()
                if clean_value:
                    clean_custom_fields[clean_key] = clean_value
        if clean_custom_fields:
            normalized["custom_fields"] = clean_custom_fields

    return normalized


def saved_filter_href(project_key: str, filter_id: str) -> str:
    return f"/dashboard/{project_key}/list?{urlencode({'saved_filter': filter_id})}"


def filter_params_from_form(
    *,
    view: str,
    kind: list[str] | None,
    status: list[str] | None,
    tag: list[str] | None,
    applies_to: list[str] | None,
    relation_type: list[str] | None,
    include_deleted: bool,
    custom_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    return normalize_filter_params({
        "view": view,
        "kind": kind,
        "status": status,
        "tag": tag,
        "applies_to": applies_to,
        "relation_type": relation_type,
        "custom_fields": custom_fields,
        "include_deleted": include_deleted,
    })


def _store_path(data_dir: Path) -> Path:
    return data_dir / "dashboard_filters.json"


def _read_store(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"projects": {}}
    except json.JSONDecodeError:
        return {"projects": {}}
    if not isinstance(raw, dict):
        return {"projects": {}}
    projects = raw.get("projects")
    if not isinstance(projects, dict):
        raw["projects"] = {}
    return raw


def _write_store(path: Path, store: dict) -> None:
    path.write_text(
        json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-")
    return slug[:64] or "filter"


def _unique_filter_id(raw_filters: list[dict], base: str) -> str:
    existing_ids = {raw.get("id") for raw in raw_filters if isinstance(raw, dict)}
    if base not in existing_ids:
        return base
    i = 2
    while f"{base}-{i}" in existing_ids:
        i += 1
    return f"{base}-{i}"


def _normalize_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    clean: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if stripped and stripped not in clean:
            clean.append(stripped)
    return clean
