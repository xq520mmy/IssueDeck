"""Shared custom-field normalization helpers for items."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from issuedeck.core.errors import InvalidCustomField

CustomFieldFilterOp = Literal["eq", "gt", "gte", "lt", "lte", "present", "missing"]
_FILTER_SUFFIXES: tuple[tuple[str, CustomFieldFilterOp], ...] = (
    ("__min", "gte"),
    ("__max", "lte"),
    ("__gt", "gt"),
    ("__lt", "lt"),
    ("__presence", "present"),
)
_FILTER_OPTION_RE = re.compile(
    r"^\s*([a-z][a-z0-9_-]{0,63})\s*(>=|<=|>|<|=|:)\s*(.*?)\s*$"
)


@dataclass(frozen=True)
class CustomFieldFilter:
    key: str
    op: CustomFieldFilterOp
    value: object | None = None


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
) -> list[CustomFieldFilter]:
    fields = project_cfg.custom_fields

    result: list[CustomFieldFilter] = []
    for raw_key, raw in incoming.items():
        key, op = _split_filter_key(project_cfg, raw_key)
        cfg = fields[key]
        if op in {"gt", "gte", "lt", "lte"}:
            if cfg.type != "number":
                raise InvalidCustomField(
                    f"custom field '{key}' only supports range filters for number fields",
                    details={"project_key": project_cfg.key, "field": key},
                )
            value = normalize_custom_field_value(project_cfg.key, key, cfg, raw)
            if value is not None:
                result.append(CustomFieldFilter(key=key, op=op, value=value))
            continue
        if op == "present":
            presence = _normalize_presence(raw)
            if presence is not None:
                result.append(CustomFieldFilter(key=key, op=presence))
            continue

        value = normalize_custom_field_value(project_cfg.key, key, cfg, raw)
        if value is not None:
            result.append(CustomFieldFilter(key=key, op="eq", value=value))
    return result


def parse_custom_field_filter_options(
    project_cfg,
    options: list[str] | None,
) -> dict[str, object]:
    incoming: dict[str, object] = {}
    for option in options or []:
        parsed = _parse_filter_option(project_cfg, option)
        if parsed is None:
            raise InvalidCustomField(
                f"invalid custom field filter '{option}'; "
                "expected FIELD=VALUE, FIELD>=VALUE, or FIELD:present",
                details={"project_key": project_cfg.key, "filter": option},
            )
        key, op, value = parsed
        incoming[_filter_key_for_op(key, op)] = value
    return incoming


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


def _split_filter_key(project_cfg, raw_key: str) -> tuple[str, CustomFieldFilterOp]:
    fields = project_cfg.custom_fields
    key = raw_key.strip()
    if key in fields:
        return key, "eq"
    for suffix, op in _FILTER_SUFFIXES:
        if key.endswith(suffix) and key[:-len(suffix)] in fields:
            return key[:-len(suffix)], op
    raise InvalidCustomField(
        f"unknown custom field filter '{raw_key}'",
        details={"project_key": project_cfg.key, "field": raw_key},
    )


def _parse_filter_option(
    project_cfg,
    raw: str,
) -> tuple[str, CustomFieldFilterOp, object] | None:
    match = _FILTER_OPTION_RE.match(raw)
    if not match:
        return None
    key, op_token, raw_value = match.groups()
    if key not in project_cfg.custom_fields:
        raise InvalidCustomField(
            f"unknown custom field filter '{key}'",
            details={"project_key": project_cfg.key, "field": key},
        )
    if op_token == ":":
        presence = _normalize_presence(raw_value)
        if presence is None:
            raise InvalidCustomField(
                f"custom field '{key}' presence filter must be present or missing",
                details={"project_key": project_cfg.key, "field": key},
            )
        return key, "present", presence
    op: CustomFieldFilterOp = {
        "=": "eq",
        ">": "gt",
        ">=": "gte",
        "<": "lt",
        "<=": "lte",
    }[op_token]
    if op == "eq" and raw_value == "*":
        return key, "present", "present"
    return key, op, raw_value


def _filter_key_for_op(key: str, op: CustomFieldFilterOp) -> str:
    if op == "eq":
        return key
    if op == "gte":
        return f"{key}__min"
    if op == "lte":
        return f"{key}__max"
    if op == "present":
        return f"{key}__presence"
    return f"{key}__{op}"


def _normalize_presence(raw: object) -> CustomFieldFilterOp | None:
    if isinstance(raw, bool):
        return "present" if raw else "missing"
    value = str(raw).strip().lower()
    if value in {"", "any"}:
        return None
    if value in {"1", "true", "yes", "on", "*", "present", "exists", "has"}:
        return "present"
    if value in {"0", "false", "no", "off", "missing", "empty", "none"}:
        return "missing"
    return None
