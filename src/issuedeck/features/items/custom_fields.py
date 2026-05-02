"""Shared custom-field normalization helpers for items."""

from __future__ import annotations

import json
from typing import Any

from issuedeck.core.errors import InvalidCustomField


def custom_fields_from_json(raw: str) -> dict[str, object]:
    try:
        values = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return values if isinstance(values, dict) else {}


def custom_fields_to_json(values: dict[str, object]) -> str:
    return json.dumps(values, ensure_ascii=False, sort_keys=True)


def normalize_custom_fields(
    project_cfg,
    incoming: dict[str, object],
    *,
    existing: dict[str, object] | None = None,
) -> dict[str, object]:
    fields = project_cfg.custom_fields
    unknown = sorted(set(incoming) - set(fields))
    if unknown:
        raise InvalidCustomField(
            f"unknown custom field(s): {', '.join(unknown)}",
            details={"project_key": project_cfg.key, "fields": unknown},
        )

    result = {
        key: value
        for key, value in (existing or {}).items()
        if key in fields
    }
    for key, cfg in fields.items():
        if key not in incoming:
            if existing is None and cfg.type == "checkbox":
                result[key] = False
            continue
        value = normalize_custom_field_value(project_cfg.key, key, cfg, incoming[key])
        if value is None:
            result.pop(key, None)
        else:
            result[key] = value

    missing = [
        key
        for key, cfg in fields.items()
        if cfg.required and not has_custom_field_value(result.get(key))
    ]
    if missing:
        raise InvalidCustomField(
            f"missing required custom field(s): {', '.join(missing)}",
            details={"project_key": project_cfg.key, "fields": missing},
        )
    return result


def normalize_custom_field_filters(
    project_cfg,
    incoming: dict[str, object],
) -> dict[str, object]:
    fields = project_cfg.custom_fields
    unknown = sorted(set(incoming) - set(fields))
    if unknown:
        raise InvalidCustomField(
            f"unknown custom field filter(s): {', '.join(unknown)}",
            details={"project_key": project_cfg.key, "fields": unknown},
        )

    result: dict[str, object] = {}
    for key, raw in incoming.items():
        cfg = fields[key]
        value = normalize_custom_field_value(project_cfg.key, key, cfg, raw)
        if value is not None:
            result[key] = value
    return result


def parse_custom_field_filter_options(
    project_cfg,
    options: list[str] | None,
) -> dict[str, object]:
    incoming: dict[str, object] = {}
    for option in options or []:
        if "=" not in option:
            raise InvalidCustomField(
                f"invalid custom field filter '{option}'; expected FIELD=VALUE",
                details={"project_key": project_cfg.key, "filter": option},
            )
        key, value = option.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            incoming[key] = value
    return normalize_custom_field_filters(project_cfg, incoming)


def normalize_custom_field_value(
    project_key: str,
    key: str,
    cfg,
    raw: object,
) -> object | None:
    if cfg.type == "checkbox":
        return coerce_bool(raw)
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if cfg.type == "number":
        try:
            return float(value) if "." in value else int(value)
        except ValueError as exc:
            raise InvalidCustomField(
                f"custom field '{key}' must be a number",
                details={"project_key": project_key, "field": key},
            ) from exc
    if cfg.type == "select" and value not in cfg.options:
        raise InvalidCustomField(
            f"custom field '{key}' must be one of: {', '.join(cfg.options)}",
            details={"project_key": project_key, "field": key, "options": cfg.options},
        )
    return value


def coerce_bool(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int | float):
        return bool(raw)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def has_custom_field_value(value: Any | None) -> bool:
    if isinstance(value, bool):
        return value
    return value is not None and value != ""
