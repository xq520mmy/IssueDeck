"""Dashboard routes — server-rendered Jinja2 pages with HTMX interactions."""

from __future__ import annotations

import hmac
import json
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import func, select

from issuedeck.core.auth import (
    DASHBOARD_SESSION_COOKIE,
    DASHBOARD_SESSION_MAX_AGE_SECONDS,
    make_dashboard_session_cookie,
)
from issuedeck.core.config import ProjectConfig
from issuedeck.core.errors import ConfigError, IssueDeckError
from issuedeck.features.dashboard.helpers import (
    all_tags,
    count_by_field,
    kind_color,
    kind_label,
    render,
    status_color,
    status_label,
    total_count,
)
from issuedeck.features.dashboard.i18n import (
    DASHBOARD_LANG_COOKIE,
    SUPPORTED_LANGS,
    language_from_request,
    make_translator,
)
from issuedeck.features.dashboard.saved_filters import (
    delete_dashboard_filter,
    filter_params_from_form,
    get_saved_dashboard_filter,
    list_saved_dashboard_filters,
    save_dashboard_filter,
    saved_filter_href,
)
from issuedeck.features.export.md_bundle import export_audit_bundle
from issuedeck.features.items.custom_fields import normalize_custom_field_filters
from issuedeck.features.items.models import ImportBatch, Item, ItemTag
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import (
    BulkUpdateItemsRequest,
    CreateItemEventRequest,
    CreateItemRequest,
    ShipItemRequest,
    UpdateItemRequest,
)
from issuedeck.features.items.service import ItemService
from issuedeck.features.migrate.csv_items import (
    CsvImportReport,
    CsvItemMapping,
    import_csv_items,
    parse_status_map_options,
)
from issuedeck.features.migrate.github_issues import (
    fetch_github_issue_rows,
    import_github_issue_rows,
    parse_github_repo,
)
from issuedeck.features.migrate.json_items import (
    JsonImportReport,
    JsonItemMapping,
    import_json_items,
)
from issuedeck.features.migrate.markdown_tasks import (
    MarkdownTaskImportReport,
    import_markdown_task_list,
)
from issuedeck.features.projects.project_templates import (
    DEFAULT_PROJECT_TEMPLATE_KEY,
    get_project_template,
    list_project_templates,
    render_project_toml,
)
from issuedeck.features.relationships.repo import RelationshipRepo
from issuedeck.features.relationships.service import RelationshipService
from issuedeck.features.search.repo import SearchRepo
from issuedeck.features.search.service import SearchService
from issuedeck.features.work_sessions.repo import WorkSessionRepo
from issuedeck.features.work_sessions.service import WorkSessionService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

KIND_QUERY = Query(None)
STATUS_QUERY = Query(None, alias="status")
TAG_QUERY = Query(None)
APPLIES_TO_QUERY = Query(None)
RELATION_TYPE_QUERY = Query(None)
KIND_FORM = Form([])
STATUS_FORM = Form([], alias="status")
TAG_FORM = Form([])
APPLIES_TO_FORM = Form([])
BULK_LOCAL_IDS_FORM = Form([])
BULK_APPLIES_TO_FORM = Form([], alias="bulk_applies_to")
RELATION_TYPE_FORM = Form([])
NEXT_QUERY = Query("/dashboard/")
NEXT_FORM = Form("/dashboard/")
SOURCE_FILE_FORM = File(...)

WORK_QUEUE_KEYS = {
    "recent",
    "backlog",
    "active",
    "blocked",
    "ready_to_ship",
    "done",
    "deleted",
}
PROJECT_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,62}$")
IMPORT_HISTORY_SOURCES = {"all", "github", "csv", "json", "markdown"}
IMPORT_HISTORY_STATES = {"all", "active", "deleted", "mixed"}
IMPORT_HISTORY_PAGE_SIZE = 25
IMPORT_HISTORY_MAX_SCAN = 250


def _item_svc(request: Request):
    session = request.app.state.session_factory()
    registry = request.app.state.registry
    webhook_dispatcher = getattr(request.app.state, "webhook_dispatcher", None)
    return (
        ItemService(
            ItemRepo(session),
            registry,
            session,
            webhook_dispatcher=webhook_dispatcher,
        ),
        session,
    )


def _search_svc(request: Request):
    session = request.app.state.session_factory()
    registry = request.app.state.registry
    return SearchService(SearchRepo(session), registry, session), session


def _rel_svc(request: Request):
    session = request.app.state.session_factory()
    registry = request.app.state.registry
    return RelationshipService(
        RelationshipRepo(session), ItemRepo(session), registry, session,
    ), session


def _work_session_svc(request: Request):
    session = request.app.state.session_factory()
    registry = request.app.state.registry
    return (
        WorkSessionService(
            WorkSessionRepo(session),
            ItemRepo(session),
            registry,
            session,
        ),
        session,
    )


def _ctx(request: Request, project_key: str | None = None, **extra):
    """Build common template context."""
    registry = request.app.state.registry
    projects = registry.all_projects()
    project = registry.project(project_key) if project_key else None
    lang = language_from_request(request)
    t = make_translator(lang)
    return {
        "projects": projects,
        "project": project,
        "project_key": project_key,
        "lang": lang,
        "supported_langs": sorted(SUPPORTED_LANGS),
        "t": t,
        "kind_color": kind_color,
        "status_color": status_color,
        "kind_label": kind_label,
        "status_label": status_label,
        "relation_labels": {
            "blocks": t("relationship.blocks"),
            "blocked_by": t("relationship.blocked_by"),
            "related_to": t("relationship.related_to"),
        },
        "external_link_labels": {
            "github_issue": t("external_links.github_issue"),
            "github_pr": t("external_links.github_pr"),
            "github_commit": t("external_links.github_commit"),
            "other": t("external_links.other"),
        },
        "work_session_status_labels": {
            "active": t("work_session.status.active"),
            "paused": t("work_session.status.paused"),
            "completed": t("work_session.status.completed"),
            "canceled": t("work_session.status.canceled"),
        },
        **extra,
    }


def _safe_dashboard_next(next_url: str | None) -> str:
    if not next_url or next_url.startswith("//"):
        return "/dashboard/"
    if next_url in {"/dashboard", "/dashboard/"}:
        return next_url
    if next_url.startswith("/dashboard/") or next_url.startswith("/dashboard?"):
        return next_url
    return "/dashboard/"


def _dashboard_url_with_params(next_url: str, **params: object) -> str:
    parts = urlsplit(_safe_dashboard_next(next_url))
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in params
    ]
    for key, value in params.items():
        if value is not None:
            query.append((key, str(value)))
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        urlencode(query),
        parts.fragment,
    ))


def _current_dashboard_url(request: Request, *, exclude: set[str] | None = None) -> str:
    exclude = exclude or set()
    pairs = [
        (key, value)
        for key, value in request.query_params.multi_items()
        if key not in exclude
    ]
    query = urlencode(pairs)
    return request.url.path + (f"?{query}" if query else "")


def _external_links_from_form(raw: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for line in raw.splitlines():
        clean = line.strip()
        if not clean:
            continue
        label = None
        url = clean
        if "|" in clean:
            before, after = clean.split("|", 1)
            if after.strip():
                label = before.strip() or None
                url = after.strip()
        payload = {"url": url}
        if label:
            payload["label"] = label
        links.append(payload)
    return links


def _custom_fields_from_form(project: ProjectConfig, form_data) -> dict[str, object]:
    values: dict[str, object] = {}
    for key, cfg in project.custom_fields.items():
        form_key = f"custom_field__{key}"
        if cfg.type == "checkbox":
            values[key] = form_key in form_data
        else:
            values[key] = str(form_data.get(form_key, ""))
    return values


def _last_form_value(form_data, key: str) -> object | None:
    if hasattr(form_data, "getlist"):
        raw_values = form_data.getlist(key)
        return raw_values[-1] if raw_values else None
    if hasattr(form_data, "get"):
        return form_data.get(key)
    return None


def _custom_field_updates_from_form(
    project: ProjectConfig,
    form_data,
) -> dict[str, object]:
    values: dict[str, object] = {}
    for key, cfg in project.custom_fields.items():
        raw_value = _last_form_value(form_data, f"custom_field__{key}")
        if raw_value is None:
            continue
        text = str(raw_value).strip()
        if not text:
            continue
        if cfg.type == "checkbox" and text == "any":
            continue
        values[key] = text
    return values


def _custom_field_filters_from_form(project: ProjectConfig, form_data) -> dict[str, object]:
    incoming: dict[str, object] = {}
    for key, cfg in project.custom_fields.items():
        raw_value = _last_form_value(form_data, f"custom_field__{key}")
        if raw_value is not None:
            text = str(raw_value).strip()
            if text and not (cfg.type == "checkbox" and text == "any"):
                incoming[key] = text

        for suffix, form_prefix in (
            ("__min", "custom_field_min__"),
            ("__max", "custom_field_max__"),
            ("__gt", "custom_field_gt__"),
            ("__lt", "custom_field_lt__"),
            ("__presence", "custom_field_presence__"),
        ):
            raw_value = _last_form_value(form_data, f"{form_prefix}{key}")
            if raw_value is None:
                continue
            text = str(raw_value).strip()
            if text and text != "any":
                incoming[f"{key}{suffix}"] = text
    normalize_custom_field_filters(project, incoming)
    return incoming


def _custom_field_filter_controls(
    project: ProjectConfig,
    filters: dict[str, object],
) -> dict[str, dict[str, object]]:
    controls: dict[str, dict[str, object]] = {}
    for key, cfg in project.custom_fields.items():
        exact = filters.get(key, "")
        min_value = filters.get(f"{key}__min", "")
        max_value = filters.get(f"{key}__max", "")
        if cfg.type == "number" and exact not in ("", None):
            min_value = min_value or exact
            max_value = max_value or exact
        controls[key] = {
            "exact": exact,
            "min": min_value,
            "max": max_value,
            "presence": filters.get(f"{key}__presence", ""),
        }
    return controls


def _custom_field_filter_query(
    project: ProjectConfig,
    filters: dict[str, object],
) -> list[dict[str, object]]:
    query: list[dict[str, object]] = []
    for raw_key, value in filters.items():
        key = raw_key
        name = f"custom_field__{raw_key}"
        if raw_key not in project.custom_fields:
            for suffix, form_prefix in (
                ("__min", "custom_field_min__"),
                ("__max", "custom_field_max__"),
                ("__gt", "custom_field_gt__"),
                ("__lt", "custom_field_lt__"),
                ("__presence", "custom_field_presence__"),
            ):
                if raw_key.endswith(suffix):
                    key = raw_key[:-len(suffix)]
                    name = f"{form_prefix}{key}"
                    break
        query.append({"name": name, "value": value})
    return query


def _split_form_tokens(raw: str) -> list[str]:
    parts = re.split(r"[\n,;]+", raw)
    values: list[str] = []
    for part in parts:
        clean = part.strip()
        if clean and clean not in values:
            values.append(clean)
    return values


def _dashboard_import_batch_tag(source_type: str) -> str:
    prefix = re.sub(r"[^a-z0-9]+", "-", source_type.lower()).strip("-") or "data"
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-import-{timestamp}-{secrets.token_hex(2)}"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _status_map_options_from_text(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _default_github_import_form(project: ProjectConfig) -> dict[str, object]:
    default_kind = next(iter(project.kinds.keys()), "")
    default_status = next(
        (key for key, cfg in project.statuses.items() if not cfg.terminal),
        next(iter(project.statuses.keys()), ""),
    )
    return {
        "repo": "",
        "kind": default_kind,
        "default_status": default_status,
        "state": "open",
        "limit": 50,
        "labels": "",
        "tags": "",
        "status_maps": "closed=done" if "done" in project.statuses else "",
        "include_pulls": False,
        "applies_to": [branch.key for branch in project.branches],
    }


def _default_data_import_form(project: ProjectConfig) -> dict[str, object]:
    default_kind = next(iter(project.kinds.keys()), "")
    default_status = next(
        (key for key, cfg in project.statuses.items() if not cfg.terminal),
        next(iter(project.statuses.keys()), ""),
    )
    return {
        "source_type": "csv",
        "kind": default_kind,
        "default_status": default_status,
        "tags": "",
        "status_maps": "closed=done" if "done" in project.statuses else "",
        "presets": "",
        "field_aliases": "",
        "include_checked": False,
        "applies_to": [branch.key for branch in project.branches],
    }


def _data_import_extension(source_type: str) -> str:
    return {
        "csv": ".csv",
        "json": ".json",
        "markdown": ".md",
    }[source_type]


def _data_import_result(
    *,
    project_key: str,
    source_type: str,
    filename: str,
    dry_run: bool,
    batch_tag: str | None,
    report: CsvImportReport | JsonImportReport | MarkdownTaskImportReport,
) -> dict[str, object]:
    items_written = report.items_written
    triage_url = (
        _dashboard_url_with_params(
            f"/dashboard/{project_key}/list",
            tag=batch_tag,
        )
        if batch_tag and items_written
        else None
    )
    if source_type == "markdown":
        stats = [
            ("data_import.tasks_found", report.tasks_found),
            ("data_import.checked_tasks", report.checked_tasks),
            ("data_import.skipped_checked", report.skipped_checked),
            ("data_import.planned", report.items_planned),
            ("data_import.written", report.items_written),
            ("data_import.external_links", report.external_links),
        ]
    elif source_type == "json":
        stats = [
            ("data_import.objects_found", report.objects_found),
            ("data_import.objects_skipped", report.objects_skipped),
            ("data_import.planned", report.items_planned),
            ("data_import.written", report.items_written),
            ("data_import.status_mapped", report.status_mapped),
            ("data_import.custom_fields", report.custom_fields),
            ("data_import.external_links", report.external_links),
        ]
    else:
        stats = [
            ("data_import.rows_found", report.rows_found),
            ("data_import.rows_skipped", report.rows_skipped),
            ("data_import.planned", report.items_planned),
            ("data_import.written", report.items_written),
            ("data_import.status_mapped", report.status_mapped),
            ("data_import.custom_fields", report.custom_fields),
            ("data_import.external_links", report.external_links),
        ]
    return {
        "mode": "dry_run" if dry_run else "import",
        "source_type": source_type,
        "filename": filename or f"upload{_data_import_extension(source_type)}",
        "stats": stats,
        "batch_tag": batch_tag if items_written else None,
        "triage_url": triage_url,
    }


def _data_import_skipped_count(
    source_type: str,
    report: CsvImportReport | JsonImportReport | MarkdownTaskImportReport,
) -> int:
    if source_type == "markdown":
        return report.skipped_checked
    if source_type == "json":
        return report.objects_skipped
    return report.rows_skipped


async def _record_import_batch(
    session,
    *,
    project_key: str,
    batch_tag: str | None,
    source_type: str,
    source_name: str,
    items_planned: int,
    items_written: int,
    skipped_count: int = 0,
    status_mapped: int = 0,
    external_links: int = 0,
    metadata: dict[str, object] | None = None,
) -> None:
    if not batch_tag or items_written <= 0:
        return
    session.add(ImportBatch(
        project_key=project_key,
        batch_tag=batch_tag,
        source_type=source_type,
        source_name=source_name,
        items_planned=items_planned,
        items_written=items_written,
        skipped_count=skipped_count,
        status_mapped=status_mapped,
        external_links=external_links,
        created_at=_iso_now(),
        metadata_json=json.dumps(metadata or {}, sort_keys=True),
    ))
    await session.commit()


async def _import_batch_item_counts(
    session,
    *,
    project_key: str,
    batch_tags: list[str],
) -> dict[str, dict[str, int]]:
    counts = {
        tag: {"active_items": 0, "deleted_items": 0}
        for tag in batch_tags
    }
    if not batch_tags:
        return counts

    result = await session.execute(
        select(ItemTag.tag, Item.deleted_at, func.count())
        .join(Item, Item.pk == ItemTag.item_pk)
        .where(Item.project_key == project_key, ItemTag.tag.in_(batch_tags))
        .group_by(ItemTag.tag, Item.deleted_at)
    )
    for tag, deleted_at, item_count in result.all():
        bucket = "active_items" if deleted_at is None else "deleted_items"
        counts.setdefault(tag, {"active_items": 0, "deleted_items": 0})[bucket] += item_count
    return counts


def _import_batch_view(
    project_key: str,
    batch: ImportBatch,
    item_counts: dict[str, dict[str, int]],
) -> dict[str, object]:
    counts = item_counts.get(batch.batch_tag, {})
    return {
        "batch_tag": batch.batch_tag,
        "source_type": batch.source_type,
        "source_name": batch.source_name,
        "items_planned": batch.items_planned,
        "items_written": batch.items_written,
        "active_items": counts.get("active_items", 0),
        "deleted_items": counts.get("deleted_items", 0),
        "skipped_count": batch.skipped_count,
        "status_mapped": batch.status_mapped,
        "external_links": batch.external_links,
        "created_at": batch.created_at,
        "triage_url": _dashboard_url_with_params(
            f"/dashboard/{project_key}/list",
            tag=batch.batch_tag,
        ),
    }


def _filter_import_batch_views(
    batches: list[dict[str, object]],
    *,
    batch_state: str,
) -> list[dict[str, object]]:
    if batch_state == "active":
        return [batch for batch in batches if batch["active_items"] > 0]
    if batch_state == "deleted":
        return [
            batch for batch in batches
            if batch["active_items"] == 0 and batch["deleted_items"] > 0
        ]
    if batch_state == "mixed":
        return [
            batch for batch in batches
            if batch["active_items"] > 0 and batch["deleted_items"] > 0
        ]
    return batches


async def _local_ids_for_import_batch(
    svc: ItemService,
    project_key: str,
    batch_tag: str,
    *,
    include_deleted: bool = False,
    only_deleted: bool = False,
) -> list[str]:
    local_ids: list[str] = []
    after = None
    while True:
        result = await svc.list_items(
            project_key,
            tags=[batch_tag],
            include_deleted=include_deleted,
            only_deleted=only_deleted,
            limit=500,
            after=after,
        )
        local_ids.extend(item.local_id for item in result.items)
        if not result.next_cursor:
            return local_ids
        after = result.next_cursor


async def _active_local_ids_for_import_batch(
    svc: ItemService,
    project_key: str,
    batch_tag: str,
) -> list[str]:
    return await _local_ids_for_import_batch(
        svc, project_key, batch_tag, include_deleted=False,
    )


async def _deleted_local_ids_for_import_batch(
    svc: ItemService,
    project_key: str,
    batch_tag: str,
) -> list[str]:
    return await _local_ids_for_import_batch(
        svc, project_key, batch_tag, include_deleted=True, only_deleted=True,
    )


def _chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[idx:idx + size] for idx in range(0, len(values), size)]


def _work_queue_statuses(project: ProjectConfig, view: str) -> list[str] | None:
    status_keys = list(project.statuses.keys())
    if not status_keys:
        return None

    first_status = status_keys[0]
    non_terminal = [
        key for key, cfg in project.statuses.items() if not cfg.terminal
    ]
    terminal = [key for key, cfg in project.statuses.items() if cfg.terminal]

    if view == "backlog":
        return [first_status]
    if view == "active":
        return [key for key in non_terminal if key != first_status] or non_terminal
    if view == "ready_to_ship":
        for idx, (_key, cfg) in enumerate(project.statuses.items()):
            if cfg.requires_ship:
                before_ship = [
                    key for key in status_keys[:idx]
                    if not project.statuses[key].terminal
                ]
                return before_ship[-1:] or non_terminal
        return non_terminal[-1:] or None
    if view == "done":
        return terminal or (["done"] if "done" in project.statuses else None)
    return None


def _work_queue_filters(project: ProjectConfig, view: str) -> dict:
    view = view if view in WORK_QUEUE_KEYS else "recent"
    filters: dict = {
        "statuses": _work_queue_statuses(project, view),
        "relationship_types": None,
        "include_deleted": False,
        "only_deleted": False,
    }
    if view == "blocked":
        filters["relationship_types"] = ["blocked_by"]
    elif view == "deleted":
        filters["include_deleted"] = True
        filters["only_deleted"] = True
    return filters


def _overview_onboarding_steps(
    project_key: str,
    project: ProjectConfig,
    total: int,
    status_counts: dict[str, int],
) -> list[dict[str, object]]:
    terminal_count = sum(
        status_counts.get(key, 0)
        for key, cfg in project.statuses.items()
        if cfg.terminal
    )
    active_count = sum(
        status_counts.get(key, 0)
        for key, cfg in project.statuses.items()
        if not cfg.terminal
    )
    ready_view = "done" if terminal_count else "ready_to_ship"
    return [
        {
            "complete": True,
            "title": "onboarding.step_project_title",
            "body": "onboarding.step_project_body",
            "href": "/dashboard/projects-new",
            "action": "onboarding.step_project_action",
        },
        {
            "complete": total > 0,
            "title": "onboarding.step_item_title",
            "body": "onboarding.step_item_body",
            "href": f"/dashboard/{project_key}/items-new",
            "action": "onboarding.step_item_action",
        },
        {
            "complete": active_count > 0,
            "title": "onboarding.step_queue_title",
            "body": "onboarding.step_queue_body",
            "href": f"/dashboard/{project_key}/list?view=active",
            "action": "onboarding.step_queue_action",
        },
        {
            "complete": terminal_count > 0,
            "title": "onboarding.step_ship_title",
            "body": "onboarding.step_ship_body",
            "href": f"/dashboard/{project_key}/list?view={ready_view}",
            "action": "onboarding.step_ship_action",
        },
    ]


def _work_queue_nav(project_key: str, active_view: str) -> list[dict[str, str | bool]]:
    queues = [
        ("recent", "Recently touched", "Clock"),
        ("backlog", "Backlog", "Inbox"),
        ("active", "Active", "Play"),
        ("blocked", "Blocked", "Block"),
        ("ready_to_ship", "Ready to ship", "Ship"),
        ("done", "Done", "Check"),
        ("deleted", "Deleted", "Trash"),
    ]
    return [
        {
            "key": key,
            "label": label,
            "icon": icon,
            "href": f"/dashboard/{project_key}/list?view={key}",
            "active": key == active_view,
        }
        for key, label, icon in queues
    ]


def _project_form_context(
    *,
    registry,
    error: str | None = None,
    form: dict[str, object] | None = None,
    status_code: int = 200,
) -> dict[str, object]:
    return {
        "active_page": "new_project",
        "error": error,
        "form": form or {"template_key": DEFAULT_PROJECT_TEMPLATE_KEY},
        "project_templates": list_project_templates(
            registry.server.project_templates_dir
        ),
        "default_template_key": DEFAULT_PROJECT_TEMPLATE_KEY,
        "status_code": status_code,
    }


# ---------------------------------------------------------------------------
# Browser auth
# ---------------------------------------------------------------------------

@router.get("/login")
async def dashboard_login_page(request: Request, next: str = NEXT_QUERY):
    return render(
        "pages/login.html", request,
        **_ctx(request),
        next_url=_safe_dashboard_next(next),
        error=None,
    )


@router.post("/login")
async def dashboard_login_submit(
    request: Request,
    token: str = Form(...),
    next: str = NEXT_FORM,
):
    server_cfg = request.app.state.registry.server
    next_url = _safe_dashboard_next(next)
    matched_token = None
    for credential in server_cfg.auth_tokens():
        if "admin" not in credential.normalized_scopes():
            continue
        value = credential.token.get_secret_value()
        if hmac.compare_digest(token, value):
            matched_token = value
            break
    if matched_token is None:
        return render(
            "pages/login.html", request,
            **_ctx(request),
            next_url=next_url,
            error=make_translator(language_from_request(request))("auth.invalid_token"),
            status_code=401,
        )

    response = RedirectResponse(url=next_url, status_code=303)
    response.set_cookie(
        DASHBOARD_SESSION_COOKIE,
        make_dashboard_session_cookie(matched_token),
        max_age=DASHBOARD_SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/dashboard",
    )
    return response


@router.post("/logout")
async def dashboard_logout():
    response = RedirectResponse(url="/dashboard/login", status_code=303)
    response.delete_cookie(DASHBOARD_SESSION_COOKIE, path="/dashboard")
    return response


@router.post("/language")
async def dashboard_language(
    lang: str = Form(...),
    next: str = NEXT_FORM,
):
    response = RedirectResponse(url=_safe_dashboard_next(next), status_code=303)
    if lang in SUPPORTED_LANGS:
        response.set_cookie(
            DASHBOARD_LANG_COOKIE,
            lang,
            max_age=60 * 60 * 24 * 365,
            httponly=False,
            samesite="lax",
            path="/dashboard",
        )
    return response


# ---------------------------------------------------------------------------
# Home redirect
# ---------------------------------------------------------------------------

@router.get("/")
async def dashboard_home(request: Request):
    projects = request.app.state.registry.all_projects()
    if not projects:
        return render("pages/home.html", request, **_ctx(request), empty=True)
    response = RedirectResponse(
        url=f"/dashboard/{projects[0].key}", status_code=302,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Project creation
# ---------------------------------------------------------------------------

@router.get("/projects-new")
async def create_project_form(request: Request):
    registry = request.app.state.registry
    return render(
        "pages/project_form.html", request,
        **_ctx(request),
        **_project_form_context(registry=registry),
    )


@router.post("/projects-new")
async def create_project_submit(
    request: Request,
    key: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    template_key: str = Form(DEFAULT_PROJECT_TEMPLATE_KEY),
):
    registry = request.app.state.registry
    key = key.strip().lower()
    name = name.strip()
    description = description.strip()
    template_key = template_key.strip()
    template = get_project_template(
        template_key,
        registry.server.project_templates_dir,
    )
    t = make_translator(language_from_request(request))
    form = {
        "key": key,
        "name": name,
        "description": description,
        "template_key": template_key,
    }

    error = None
    if not PROJECT_KEY_RE.fullmatch(key):
        error = t("project_form.error.invalid_key")
    elif not name:
        error = t("project_form.error.name_required")
    elif key in {p.key for p in registry.all_projects()}:
        error = t("project_form.error.exists", key=key)
    elif template is None:
        error = t("project_form.error.invalid_template")

    if error:
        return render(
            "pages/project_form.html", request,
            **_ctx(request),
            **_project_form_context(
                registry=registry,
                error=error,
                form=form,
                status_code=422,
            ),
        )

    path = registry.server.projects_dir / f"{key}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return render(
            "pages/project_form.html", request,
            **_ctx(request),
            **_project_form_context(
                registry=registry,
                error=t("project_form.error.exists_on_disk", name=path.name),
                form=form,
                status_code=409,
            ),
        )

    path.write_text(
        render_project_toml(
            key=key,
            name=name,
            description=description,
            template=template,
        ),
        encoding="utf-8",
    )

    from issuedeck.core.config import load_project_config

    try:
        project = load_project_config(path)
        registry.register_project(project)
    except ConfigError as exc:
        path.unlink(missing_ok=True)
        return render(
            "pages/project_form.html", request,
            **_ctx(request),
            **_project_form_context(
                registry=registry,
                error=str(exc),
                form=form,
                status_code=422,
            ),
        )

    return RedirectResponse(url=f"/dashboard/{key}", status_code=303)


# ---------------------------------------------------------------------------
# Project exports
# ---------------------------------------------------------------------------

@router.get("/{project_key}/exports/audit-bundle")
async def download_audit_bundle(project_key: str, request: Request):
    registry = request.app.state.registry
    registry.project(project_key)
    session = request.app.state.session_factory()
    try:
        with TemporaryDirectory() as tmp:
            report = await export_audit_bundle(
                session=session,
                registry=registry,
                project_key=project_key,
                out_path=Path(tmp) / f"{project_key}-audit-bundle.zip",
            )
            content = report.bundle_path.read_bytes()
    finally:
        await session.close()

    filename = f"{project_key}-audit-bundle.zip"
    response = Response(content=content, media_type="application/zip")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Project overview
# ---------------------------------------------------------------------------

@router.get("/{project_key}")
async def project_overview(project_key: str, request: Request):
    registry = request.app.state.registry
    registry.project(project_key)  # 404 if missing

    session = request.app.state.session_factory()
    try:
        status_counts = await count_by_field(session, project_key, "status")
        kind_counts = await count_by_field(session, project_key, "kind")
        total = await total_count(session, project_key)
    finally:
        await session.close()

    svc, session = _item_svc(request)
    try:
        recent = await svc.list_items(project_key, limit=10)
    finally:
        await session.close()

    work_svc, session = _work_session_svc(request)
    try:
        active_work_sessions = await work_svc.list_sessions(
            project_key,
            statuses=["active", "paused"],
            limit=8,
        )
    finally:
        await session.close()

    project = registry.project(project_key)

    # Build chart data
    status_chart = {
        "labels": [status_label(s, project) for s in project.statuses],
        "data": [status_counts.get(s, 0) for s in project.statuses],
        "colors": [_chart_color(s, "status") for s in project.statuses],
    }
    kind_chart = {
        "labels": [kind_label(k, project) for k in project.kinds],
        "data": [kind_counts.get(k, 0) for k in project.kinds],
        "colors": [_chart_color(k, "kind") for k in project.kinds],
    }

    return render(
        "pages/home.html", request,
        **_ctx(request, project_key),
        total=total,
        status_counts=status_counts,
        kind_counts=kind_counts,
        recent_items=recent.items,
        active_work_sessions=active_work_sessions.sessions,
        show_setup_checklist=total <= 8,
        setup_checklist_steps=_overview_onboarding_steps(
            project_key, project, total, status_counts,
        ),
        status_chart_json=json.dumps(status_chart),
        kind_chart_json=json.dumps(kind_chart),
        active_page="overview",
    )


# ---------------------------------------------------------------------------
# Import history
# ---------------------------------------------------------------------------

@router.get("/{project_key}/imports")
async def import_history_page(
    project_key: str,
    request: Request,
    source: str = Query("all"),
    batch_state: str = Query("all"),
    page: int = Query(1),
    deleted_count: int | None = Query(None),
    restored_count: int | None = Query(None),
    delete_empty: bool = Query(False),
    restore_empty: bool = Query(False),
    delete_missing: bool = Query(False),
    restore_missing: bool = Query(False),
):
    request.app.state.registry.project(project_key)
    selected_source = source if source in IMPORT_HISTORY_SOURCES else "all"
    selected_batch_state = (
        batch_state if batch_state in IMPORT_HISTORY_STATES else "all"
    )
    current_page = max(page, 1)
    session = request.app.state.session_factory()
    try:
        stmt = (
            select(ImportBatch)
            .where(ImportBatch.project_key == project_key)
            .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
            .limit(IMPORT_HISTORY_MAX_SCAN)
        )
        if selected_source != "all":
            stmt = stmt.where(ImportBatch.source_type == selected_source)
        result = await session.execute(
            stmt
        )
        batch_rows = list(result.scalars().all())
        item_counts = await _import_batch_item_counts(
            session,
            project_key=project_key,
            batch_tags=[batch.batch_tag for batch in batch_rows],
        )
        batches = [
            _import_batch_view(project_key, batch, item_counts)
            for batch in batch_rows
        ]
        batches = _filter_import_batch_views(
            batches, batch_state=selected_batch_state,
        )
    finally:
        await session.close()

    total_matches = len(batches)
    page_start = (current_page - 1) * IMPORT_HISTORY_PAGE_SIZE
    page_end = page_start + IMPORT_HISTORY_PAGE_SIZE
    page_batches = batches[page_start:page_end]
    has_previous_page = current_page > 1
    has_next_page = page_end < total_matches
    previous_page_url = (
        _dashboard_url_with_params(
            f"/dashboard/{project_key}/imports",
            source=selected_source,
            batch_state=selected_batch_state,
            page=current_page - 1,
        )
        if has_previous_page else None
    )
    next_page_url = (
        _dashboard_url_with_params(
            f"/dashboard/{project_key}/imports",
            source=selected_source,
            batch_state=selected_batch_state,
            page=current_page + 1,
        )
        if has_next_page else None
    )

    return render(
        "pages/import_history.html", request,
        **_ctx(request, project_key),
        active_page="import_history",
        batches=page_batches,
        selected_source=selected_source,
        selected_batch_state=selected_batch_state,
        current_page=current_page,
        total_matches=total_matches,
        page_start=page_start + 1 if page_batches else 0,
        page_end=page_start + len(page_batches),
        previous_page_url=previous_page_url,
        next_page_url=next_page_url,
        deleted_count=deleted_count,
        restored_count=restored_count,
        delete_empty=delete_empty,
        restore_empty=restore_empty,
        delete_missing=delete_missing,
        restore_missing=restore_missing,
    )


@router.post("/{project_key}/imports/{batch_tag}/delete")
async def import_batch_delete(
    project_key: str,
    batch_tag: str,
    request: Request,
):
    request.app.state.registry.project(project_key)
    svc, session = _item_svc(request)
    try:
        batch = await session.scalar(
            select(ImportBatch).where(
                ImportBatch.project_key == project_key,
                ImportBatch.batch_tag == batch_tag,
            )
        )
        redirect_base = f"/dashboard/{project_key}/imports"
        if batch is None:
            return RedirectResponse(
                url=_dashboard_url_with_params(redirect_base, delete_missing=1),
                status_code=303,
            )

        local_ids = await _active_local_ids_for_import_batch(
            svc, project_key, batch_tag,
        )
        if not local_ids:
            return RedirectResponse(
                url=_dashboard_url_with_params(redirect_base, delete_empty=1),
                status_code=303,
            )

        deleted_count = 0
        for chunk in _chunked(local_ids, 500):
            result = await svc.bulk_update(
                project_key,
                BulkUpdateItemsRequest(
                    local_ids=chunk,
                    action="delete",
                    reason=f"Deleted import batch {batch_tag}.",
                ),
            )
            deleted_count += result.updated_count
    finally:
        await session.close()

    return RedirectResponse(
        url=_dashboard_url_with_params(
            f"/dashboard/{project_key}/imports",
            deleted_count=deleted_count,
        ),
        status_code=303,
    )


@router.post("/{project_key}/imports/{batch_tag}/restore")
async def import_batch_restore(
    project_key: str,
    batch_tag: str,
    request: Request,
):
    request.app.state.registry.project(project_key)
    svc, session = _item_svc(request)
    try:
        batch = await session.scalar(
            select(ImportBatch).where(
                ImportBatch.project_key == project_key,
                ImportBatch.batch_tag == batch_tag,
            )
        )
        redirect_base = f"/dashboard/{project_key}/imports"
        if batch is None:
            return RedirectResponse(
                url=_dashboard_url_with_params(redirect_base, restore_missing=1),
                status_code=303,
            )

        local_ids = await _deleted_local_ids_for_import_batch(
            svc, project_key, batch_tag,
        )
        if not local_ids:
            return RedirectResponse(
                url=_dashboard_url_with_params(redirect_base, restore_empty=1),
                status_code=303,
            )

        restored_count = 0
        for chunk in _chunked(local_ids, 500):
            result = await svc.bulk_update(
                project_key,
                BulkUpdateItemsRequest(local_ids=chunk, action="restore"),
            )
            restored_count += result.updated_count
    finally:
        await session.close()

    return RedirectResponse(
        url=_dashboard_url_with_params(
            f"/dashboard/{project_key}/imports",
            restored_count=restored_count,
        ),
        status_code=303,
    )


# ---------------------------------------------------------------------------
# GitHub Issues import
# ---------------------------------------------------------------------------

@router.get("/{project_key}/imports/github")
async def github_import_form(project_key: str, request: Request):
    registry = request.app.state.registry
    project = registry.project(project_key)
    return render(
        "pages/github_import.html", request,
        **_ctx(request, project_key),
        active_page="import_github",
        form=_default_github_import_form(project),
        result=None,
        error=None,
    )


@router.post("/{project_key}/imports/github")
async def github_import_submit(
    project_key: str,
    request: Request,
    repo: str = Form(...),
    kind: str = Form(...),
    default_status: str = Form(""),
    state: str = Form("open"),
    limit: int = Form(50),
    labels: str = Form(""),
    tags: str = Form(""),
    status_maps: str = Form(""),
    github_token: str = Form(""),
    include_pulls: bool = Form(False),
    mode: str = Form("dry_run"),
    applies_to: list[str] = APPLIES_TO_FORM,
):
    registry = request.app.state.registry
    project = registry.project(project_key)
    t = make_translator(language_from_request(request))
    clean_limit = max(1, min(limit, 1000))
    dry_run = mode != "import"
    form = {
        "repo": repo.strip(),
        "kind": kind,
        "default_status": default_status.strip(),
        "state": state,
        "limit": clean_limit,
        "labels": labels,
        "tags": tags,
        "status_maps": status_maps,
        "include_pulls": include_pulls,
        "applies_to": applies_to or [],
    }

    try:
        if state not in {"open", "closed", "all"}:
            raise ValueError(t("github_import.error.invalid_state"))
        repo_ref = parse_github_repo(repo)
        item_kind = kind or next(iter(project.kinds.keys()))
        registry.validate_kind(project_key, item_kind)
        clean_default_status = default_status.strip() or None
        if clean_default_status:
            registry.validate_status(project_key, clean_default_status)
        status_map = parse_status_map_options(
            _status_map_options_from_text(status_maps)
        )
        rows, fetch_report = await fetch_github_issue_rows(
            repo_ref,
            token=github_token.strip() or None,
            state=state,
            labels=_split_form_tokens(labels),
            limit=clean_limit,
            include_pulls=include_pulls,
        )
        user_tags = _split_form_tokens(tags)
        batch_tag = None if dry_run else _dashboard_import_batch_tag("github")
        import_tags = [*user_tags, batch_tag] if batch_tag else user_tags
        session = request.app.state.session_factory()
        try:
            report = await import_github_issue_rows(
                rows,
                project_key,
                registry,
                session,
                kind=item_kind,
                default_status=clean_default_status,
                tags=import_tags,
                applies_to=applies_to if applies_to else None,
                status_map=status_map,
                dry_run=dry_run,
            )
            report.issues_fetched = fetch_report.issues_fetched
            report.pulls_skipped = fetch_report.pulls_skipped
            await _record_import_batch(
                session,
                project_key=project_key,
                batch_tag=batch_tag,
                source_type="github",
                source_name=f"{repo_ref.owner}/{repo_ref.repo}",
                items_planned=report.items_planned,
                items_written=report.items_written,
                skipped_count=report.existing_skipped + report.pulls_skipped,
                status_mapped=report.status_mapped,
                external_links=report.external_links,
                metadata={
                    "issues_fetched": report.issues_fetched,
                    "pulls_skipped": report.pulls_skipped,
                },
            )
        finally:
            await session.close()
    except httpx.HTTPError as exc:
        error = str(exc) or exc.__class__.__name__
        return render(
            "pages/github_import.html", request,
            **_ctx(request, project_key),
            active_page="import_github",
            form=form,
            result=None,
            error=error,
            status_code=422,
        )
    except (ConfigError, ValueError) as exc:
        return render(
            "pages/github_import.html", request,
            **_ctx(request, project_key),
            active_page="import_github",
            form=form,
            result=None,
            error=str(exc),
            status_code=422,
        )

    triage_url = (
        _dashboard_url_with_params(
            f"/dashboard/{project_key}/list",
            tag=batch_tag,
        )
        if batch_tag and report.items_written
        else None
    )
    result = {
        "mode": "dry_run" if dry_run else "import",
        "repo": f"{repo_ref.owner}/{repo_ref.repo}",
        "issues_fetched": report.issues_fetched,
        "pulls_skipped": report.pulls_skipped,
        "existing_skipped": report.existing_skipped,
        "items_planned": report.items_planned,
        "items_written": report.items_written,
        "status_mapped": report.status_mapped,
        "external_links": report.external_links,
        "batch_tag": batch_tag if report.items_written else None,
        "triage_url": triage_url,
    }
    return render(
        "pages/github_import.html", request,
        **_ctx(request, project_key),
        active_page="import_github",
        form=form,
        result=result,
        error=None,
    )


# ---------------------------------------------------------------------------
# CSV / JSON / Markdown imports
# ---------------------------------------------------------------------------

@router.get("/{project_key}/imports/files")
async def data_import_form(project_key: str, request: Request):
    registry = request.app.state.registry
    project = registry.project(project_key)
    return render(
        "pages/data_import.html", request,
        **_ctx(request, project_key),
        active_page="import_files",
        form=_default_data_import_form(project),
        result=None,
        error=None,
    )


@router.post("/{project_key}/imports/files")
async def data_import_submit(
    project_key: str,
    request: Request,
    source_type: str = Form("csv"),
    source_file: UploadFile = SOURCE_FILE_FORM,
    kind: str = Form(...),
    default_status: str = Form(""),
    tags: str = Form(""),
    status_maps: str = Form(""),
    presets: str = Form(""),
    field_aliases: str = Form(""),
    include_checked: bool = Form(False),
    mode: str = Form("dry_run"),
    applies_to: list[str] = APPLIES_TO_FORM,
):
    registry = request.app.state.registry
    project = registry.project(project_key)
    t = make_translator(language_from_request(request))
    dry_run = mode != "import"
    clean_source_type = source_type.strip().lower()
    form = {
        "source_type": clean_source_type,
        "kind": kind,
        "default_status": default_status.strip(),
        "tags": tags,
        "status_maps": status_maps,
        "presets": presets,
        "field_aliases": field_aliases,
        "include_checked": include_checked,
        "applies_to": applies_to or [],
    }

    try:
        if clean_source_type not in {"csv", "json", "markdown"}:
            raise ValueError(t("data_import.error.invalid_type"))
        item_kind = kind or next(iter(project.kinds.keys()))
        registry.validate_kind(project_key, item_kind)
        clean_default_status = default_status.strip() or None
        if clean_default_status:
            registry.validate_status(project_key, clean_default_status)

        content = await source_file.read()
        if not content.strip():
            raise ValueError(t("data_import.error.empty_file"))

        user_tags = _split_form_tokens(tags)
        batch_tag = None if dry_run else _dashboard_import_batch_tag(clean_source_type)
        import_tags = [*user_tags, batch_tag] if batch_tag else user_tags
        status_map = (
            parse_status_map_options(_status_map_options_from_text(status_maps))
            if clean_source_type in {"csv", "json"}
            else {}
        )
        filename = Path(source_file.filename or "").name
        suffix = _data_import_extension(clean_source_type)

        with TemporaryDirectory(prefix="issuedeck-import-") as tmpdir:
            source_path = Path(tmpdir) / f"upload{suffix}"
            source_path.write_bytes(content)
            session = request.app.state.session_factory()
            try:
                if clean_source_type == "csv":
                    mapping = CsvItemMapping.from_alias_options(
                        _status_map_options_from_text(field_aliases),
                        presets=_split_form_tokens(presets),
                    )
                    report = await import_csv_items(
                        source_path,
                        project_key,
                        registry,
                        session,
                        kind=item_kind,
                        default_status=clean_default_status,
                        tags=import_tags,
                        applies_to=applies_to if applies_to else None,
                        status_map=status_map,
                        mapping=mapping,
                        dry_run=dry_run,
                    )
                elif clean_source_type == "json":
                    mapping = JsonItemMapping.from_alias_options(
                        _status_map_options_from_text(field_aliases),
                        presets=_split_form_tokens(presets),
                    )
                    report = await import_json_items(
                        source_path,
                        project_key,
                        registry,
                        session,
                        kind=item_kind,
                        default_status=clean_default_status,
                        tags=import_tags,
                        applies_to=applies_to if applies_to else None,
                        status_map=status_map,
                        mapping=mapping,
                        dry_run=dry_run,
                    )
                else:
                    report = await import_markdown_task_list(
                        source_path,
                        project_key,
                        registry,
                        session,
                        kind=item_kind,
                        tags=import_tags,
                        applies_to=applies_to if applies_to else None,
                        include_checked=include_checked,
                        dry_run=dry_run,
                    )
                await _record_import_batch(
                    session,
                    project_key=project_key,
                    batch_tag=batch_tag,
                    source_type=clean_source_type,
                    source_name=filename or f"upload{suffix}",
                    items_planned=report.items_planned,
                    items_written=report.items_written,
                    skipped_count=_data_import_skipped_count(clean_source_type, report),
                    status_mapped=getattr(report, "status_mapped", 0),
                    external_links=report.external_links,
                    metadata={"filename": filename},
                )
            finally:
                await session.close()
    except (ConfigError, ValueError) as exc:
        return render(
            "pages/data_import.html", request,
            **_ctx(request, project_key),
            active_page="import_files",
            form=form,
            result=None,
            error=str(exc),
            status_code=422,
        )

    result = _data_import_result(
        project_key=project_key,
        source_type=clean_source_type,
        filename=filename,
        dry_run=dry_run,
        batch_tag=batch_tag,
        report=report,
    )
    return render(
        "pages/data_import.html", request,
        **_ctx(request, project_key),
        active_page="import_files",
        form=form,
        result=result,
        error=None,
    )


# ---------------------------------------------------------------------------
# Kanban
# ---------------------------------------------------------------------------

@router.get("/{project_key}/kanban")
async def kanban_board(project_key: str, request: Request):
    registry = request.app.state.registry
    project = registry.project(project_key)

    svc, session = _item_svc(request)
    try:
        result = await svc.list_items(project_key, limit=500)
    finally:
        await session.close()

    columns: dict[str, list] = {s: [] for s in project.statuses}
    for item in result.items:
        if item.status in columns:
            columns[item.status].append(item)

    return render(
        "pages/kanban.html", request,
        **_ctx(request, project_key),
        columns=columns,
        active_page="kanban",
    )


@router.patch("/{project_key}/items/{local_id}/status")
async def update_status_htmx(
    project_key: str, local_id: str, request: Request,
):
    body = await request.json()
    new_status = body.get("status", "")

    svc, session = _item_svc(request)
    try:
        item = await svc.update(project_key, local_id, UpdateItemRequest(status=new_status))
    finally:
        await session.close()

    return render(
        "components/item_card.html", request,
        is_htmx=True,
        **_ctx(request, project_key),
        item=item,
        view="kanban",
    )


# ---------------------------------------------------------------------------
# List view
# ---------------------------------------------------------------------------

@router.get("/{project_key}/list")
async def list_view(
    project_key: str, request: Request,
    view: str = "recent",
    saved_filter: str | None = None,
    kind: list[str] | None = KIND_QUERY,
    status: list[str] | None = STATUS_QUERY,
    tag: list[str] | None = TAG_QUERY,
    applies_to: list[str] | None = APPLIES_TO_QUERY,
    relation_type: list[str] | None = RELATION_TYPE_QUERY,
    include_deleted: bool = False,
    limit: int = 50,
    after: str | None = None,
    bulk_count: int | None = None,
    bulk_action: str | None = None,
    bulk_error: str | None = None,
):
    registry = request.app.state.registry
    project = registry.project(project_key)
    custom_field_filters = _custom_field_filters_from_form(project, request.query_params)
    saved_filters = list_saved_dashboard_filters(registry.server.data_dir, project_key)
    active_saved_filter = None
    if saved_filter:
        active_saved_filter = get_saved_dashboard_filter(
            registry.server.data_dir,
            project_key,
            saved_filter,
        )
        if active_saved_filter:
            params = active_saved_filter.params
            view = params.get("view", view) if isinstance(params.get("view"), str) else view
            kind = params.get("kind") if isinstance(params.get("kind"), list) else None
            status = params.get("status") if isinstance(params.get("status"), list) else None
            tag = params.get("tag") if isinstance(params.get("tag"), list) else None
            applies_to = (
                params.get("applies_to")
                if isinstance(params.get("applies_to"), list)
                else None
            )
            relation_type = (
                params.get("relation_type")
                if isinstance(params.get("relation_type"), list)
                else None
            )
            saved_custom_fields = params.get("custom_fields")
            custom_field_filters = (
                saved_custom_fields
                if isinstance(saved_custom_fields, dict)
                else {}
            )
            include_deleted = bool(params.get("include_deleted"))

    active_view = view if view in WORK_QUEUE_KEYS else "recent"
    queue_filters = _work_queue_filters(project, active_view)
    effective_status = status or queue_filters["statuses"]
    effective_relation_type = relation_type or queue_filters["relationship_types"]
    effective_include_deleted = include_deleted or queue_filters["include_deleted"]
    effective_only_deleted = queue_filters["only_deleted"]

    svc, session = _item_svc(request)
    try:
        result = await svc.list_items(
            project_key, kinds=kind, statuses=effective_status,
            tags=tag, applies_to=applies_to,
            custom_fields=custom_field_filters,
            relationship_types=effective_relation_type,
            include_deleted=effective_include_deleted,
            only_deleted=effective_only_deleted,
            limit=limit, after=after,
        )
    finally:
        await session.close()

    session2 = request.app.state.session_factory()
    try:
        tags = await all_tags(session2, project_key)
    finally:
        await session2.close()

    is_htmx = request.headers.get("HX-Request") == "true"
    custom_field_query = _custom_field_filter_query(project, custom_field_filters)

    return render(
        "pages/list.html", request,
        is_htmx=is_htmx,
        partial_template="components/item_list_content.html" if is_htmx else None,
        **_ctx(request, project_key),
        items=result.items,
        next_cursor=result.next_cursor,
        all_tags=tags,
        work_queues=_work_queue_nav(project_key, active_view),
        saved_filters=[
            {
                "id": item.id,
                "name": item.name,
                "href": saved_filter_href(project_key, item.id),
                "active": active_saved_filter is not None and item.id == active_saved_filter.id,
            }
            for item in saved_filters
        ],
        active_saved_filter=active_saved_filter,
        active_view=active_view,
        # Preserve current filters for the template
        filter_kind=kind or [],
        filter_status=status or [],
        filter_tag=tag or [],
        filter_applies_to=applies_to or [],
        filter_relation_type=relation_type or [],
        filter_custom_fields=custom_field_filters,
        filter_custom_field_controls=_custom_field_filter_controls(
            project,
            custom_field_filters,
        ),
        filter_custom_field_query=custom_field_query,
        filter_include_deleted=effective_include_deleted,
        current_list_url=_current_dashboard_url(
            request,
            exclude={"bulk_count", "bulk_action", "bulk_error"},
        ),
        bulk_count=bulk_count,
        bulk_action=bulk_action,
        bulk_error=bulk_error,
        active_page="list",
    )


@router.post("/{project_key}/items/bulk")
async def bulk_update_items_dashboard(
    project_key: str,
    request: Request,
    local_ids: list[str] = BULK_LOCAL_IDS_FORM,
    bulk_action: str = Form("update"),
    bulk_kind: str = Form(""),
    bulk_status: str = Form(""),
    bulk_tag_mode: str = Form("add"),
    bulk_tags: str = Form(""),
    bulk_branch_mode: str = Form("keep"),
    bulk_applies_to: list[str] = BULK_APPLIES_TO_FORM,
    next: str = NEXT_FORM,
):
    target_url = _safe_dashboard_next(next)
    if not local_ids:
        return RedirectResponse(
            url=_dashboard_url_with_params(
                target_url,
                bulk_error=make_translator(language_from_request(request))(
                    "bulk.error.none_selected"
                ),
                bulk_count=None,
                bulk_action=None,
            ),
            status_code=303,
        )

    try:
        project = request.app.state.registry.project(project_key)
        form_data = await request.form()
        action = bulk_action if bulk_action in {"update", "delete", "restore"} else "update"
        applies = bulk_applies_to if bulk_branch_mode == "replace" else None
        tags = _split_form_tokens(bulk_tags) if bulk_tags.strip() else None
        custom_fields = _custom_field_updates_from_form(project, form_data)
        payload = BulkUpdateItemsRequest(
            local_ids=local_ids,
            action=action,
            kind=bulk_kind.strip() or None,
            status=bulk_status.strip() or None,
            tags=tags,
            tag_mode=bulk_tag_mode if bulk_tag_mode in {"add", "remove", "replace"} else "add",
            applies_to=applies,
            custom_fields=custom_fields or None,
            reason="bulk triage",
        )
        svc, session = _item_svc(request)
        try:
            result = await svc.bulk_update(project_key, payload)
        finally:
            await session.close()
    except ValidationError as exc:
        error = exc.errors()[0]["msg"] if exc.errors() else str(exc)
        return RedirectResponse(
            url=_dashboard_url_with_params(
                target_url,
                bulk_error=error,
                bulk_count=None,
                bulk_action=None,
            ),
            status_code=303,
        )
    except IssueDeckError as exc:
        return RedirectResponse(
            url=_dashboard_url_with_params(
                target_url,
                bulk_error=exc.message,
                bulk_count=None,
                bulk_action=None,
            ),
            status_code=303,
        )

    return RedirectResponse(
        url=_dashboard_url_with_params(
            target_url,
            bulk_count=result.updated_count,
            bulk_action=result.action,
            bulk_error=None,
        ),
        status_code=303,
    )


@router.post("/{project_key}/saved-filters")
async def create_saved_filter(
    project_key: str,
    request: Request,
    name: str = Form(...),
    view: str = Form("recent"),
    kind: list[str] | None = KIND_FORM,
    status: list[str] | None = STATUS_FORM,
    tag: list[str] | None = TAG_FORM,
    applies_to: list[str] | None = APPLIES_TO_FORM,
    relation_type: list[str] | None = RELATION_TYPE_FORM,
    include_deleted: bool = Form(False),
):
    registry = request.app.state.registry
    project = registry.project(project_key)
    form_data = await request.form()
    saved_filter = save_dashboard_filter(
        registry.server.data_dir,
        project_key,
        name,
        filter_params_from_form(
            view=view,
            kind=kind,
            status=status,
            tag=tag,
            applies_to=applies_to,
            relation_type=relation_type,
            custom_fields=_custom_field_filters_from_form(project, form_data),
            include_deleted=include_deleted,
        ),
    )
    return RedirectResponse(
        url=saved_filter_href(project_key, saved_filter.id),
        status_code=303,
    )


@router.post("/{project_key}/saved-filters/{filter_id}/delete")
async def delete_saved_filter(
    project_key: str,
    filter_id: str,
    request: Request,
    next: str | None = Form(None),
):
    registry = request.app.state.registry
    registry.project(project_key)
    delete_dashboard_filter(registry.server.data_dir, project_key, filter_id)
    target_url = _safe_dashboard_next(next) if next else f"/dashboard/{project_key}/list"
    return RedirectResponse(
        url=target_url,
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Item detail
# ---------------------------------------------------------------------------

@router.get("/{project_key}/items/{local_id}")
async def item_detail(project_key: str, local_id: str, request: Request):
    svc, session = _item_svc(request)
    try:
        item = await svc.get(project_key, local_id, include_deleted=True)
    finally:
        await session.close()

    work_svc, session = _work_session_svc(request)
    try:
        work_sessions = await work_svc.list_sessions(
            project_key,
            local_id=local_id,
            limit=20,
        )
    finally:
        await session.close()

    return render(
        "pages/item_detail.html", request,
        **_ctx(request, project_key),
        item=item,
        work_sessions=work_sessions.sessions,
        active_page="detail",
    )


@router.post("/{project_key}/items/{local_id}/events")
async def add_item_event(
    project_key: str, local_id: str, request: Request,
    body: str = Form(...),
    actor_name: str = Form("dashboard"),
):
    svc, session = _item_svc(request)
    try:
        await svc.add_event(
            project_key,
            local_id,
            CreateItemEventRequest(
                event_type="comment",
                actor_type="human",
                actor_name=actor_name.strip() or "dashboard",
                body=body.strip(),
            ),
        )
    finally:
        await session.close()

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return Response(
            status_code=200,
            headers={"HX-Redirect": f"/dashboard/{project_key}/items/{local_id}"},
        )
    return RedirectResponse(
        url=f"/dashboard/{project_key}/items/{local_id}", status_code=303,
    )


# ---------------------------------------------------------------------------
# Create item
# ---------------------------------------------------------------------------

@router.get("/{project_key}/items-new")
async def create_item_form(project_key: str, request: Request):
    return render(
        "pages/item_form_page.html", request,
        **_ctx(request, project_key),
        mode="create",
        item=None,
        active_page="create",
    )


@router.post("/{project_key}/items-new")
async def create_item_submit(
    project_key: str, request: Request,
    kind: str = Form(...),
    title: str = Form(...),
    body: str = Form(""),
    tags: str = Form(""),
    external_links: str = Form(""),
    applies_to: list[str] = APPLIES_TO_FORM,
):
    project = request.app.state.registry.project(project_key)
    form_data = await request.form()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    branch_list = applies_to if applies_to else None

    svc, session = _item_svc(request)
    try:
        item = await svc.create(
            project_key,
            CreateItemRequest(
                kind=kind, title=title, body=body,
                tags=tag_list, applies_to=branch_list,
                external_links=_external_links_from_form(external_links),
                custom_fields=_custom_fields_from_form(project, form_data),
            ),
        )
    finally:
        await session.close()

    return RedirectResponse(
        url=f"/dashboard/{project_key}/items/{item.local_id}",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Edit item
# ---------------------------------------------------------------------------

@router.get("/{project_key}/items/{local_id}/edit")
async def edit_item_form(project_key: str, local_id: str, request: Request):
    svc, session = _item_svc(request)
    try:
        item = await svc.get(project_key, local_id)
    finally:
        await session.close()

    return render(
        "pages/item_form_page.html", request,
        **_ctx(request, project_key),
        mode="edit",
        item=item,
        active_page="edit",
    )


@router.post("/{project_key}/items/{local_id}/edit")
async def edit_item_submit(
    project_key: str, local_id: str, request: Request,
    title: str = Form(...),
    body: str = Form(""),
    status: str = Form(None),
    tags: str = Form(""),
    external_links: str = Form(""),
    applies_to: list[str] = APPLIES_TO_FORM,
):
    project = request.app.state.registry.project(project_key)
    form_data = await request.form()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    branch_list = applies_to if applies_to else None

    # status="done" is not allowed via update; handle gracefully
    if status == "done":
        status = None

    svc, session = _item_svc(request)
    try:
        await svc.update(
            project_key, local_id,
            UpdateItemRequest(
                title=title, body=body, status=status,
                tags=tag_list, applies_to=branch_list,
                external_links=_external_links_from_form(external_links),
                custom_fields=_custom_fields_from_form(project, form_data),
            ),
        )
    finally:
        await session.close()

    return RedirectResponse(
        url=f"/dashboard/{project_key}/items/{local_id}",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Ship item
# ---------------------------------------------------------------------------

@router.post("/{project_key}/items/{local_id}/ship")
async def ship_item(
    project_key: str, local_id: str, request: Request,
    branch: str = Form(...),
    version: str = Form(...),
    commits: str = Form(""),
):
    commit_list = [c.strip() for c in commits.split(",") if c.strip()]

    svc, session = _item_svc(request)
    try:
        await svc.ship(
            project_key, local_id,
            ShipItemRequest(branch=branch, version=version, commits=commit_list),
        )
    finally:
        await session.close()

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return Response(
            status_code=200,
            headers={"HX-Redirect": f"/dashboard/{project_key}/items/{local_id}"},
        )
    return RedirectResponse(
        url=f"/dashboard/{project_key}/items/{local_id}", status_code=303,
    )


# ---------------------------------------------------------------------------
# Delete / Restore
# ---------------------------------------------------------------------------

@router.post("/{project_key}/items/{local_id}/delete")
async def delete_item(project_key: str, local_id: str, request: Request):
    svc, session = _item_svc(request)
    try:
        await svc.soft_delete(project_key, local_id)
    finally:
        await session.close()

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return Response(
            status_code=200,
            headers={"HX-Redirect": f"/dashboard/{project_key}/list"},
        )
    return RedirectResponse(
        url=f"/dashboard/{project_key}/list", status_code=303,
    )


@router.post("/{project_key}/items/{local_id}/restore")
async def restore_item(project_key: str, local_id: str, request: Request):
    svc, session = _item_svc(request)
    try:
        await svc.restore(project_key, local_id)
    finally:
        await session.close()

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return Response(
            status_code=200,
            headers={"HX-Redirect": f"/dashboard/{project_key}/items/{local_id}"},
        )
    return RedirectResponse(
        url=f"/dashboard/{project_key}/items/{local_id}", status_code=303,
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@router.get("/{project_key}/search")
async def search_page(
    project_key: str, request: Request,
    q: str = "",
    limit: int = 50,
    after: str | None = None,
):
    items = []
    next_cursor = None

    if q.strip():
        svc, session = _search_svc(request)
        try:
            result = await svc.search(project_key, q.strip(), limit=limit, after=after)
            items = result.items
            next_cursor = result.next_cursor
        finally:
            await session.close()

    is_htmx = request.headers.get("HX-Request") == "true"

    return render(
        "pages/search.html", request,
        is_htmx=is_htmx,
        partial_template="components/search_results.html" if is_htmx else None,
        **_ctx(request, project_key),
        q=q,
        items=items,
        next_cursor=next_cursor,
        active_page="search",
    )


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------

@router.post("/{project_key}/items/{local_id}/relationships")
async def add_relationship(
    project_key: str, local_id: str, request: Request,
    to_local_id: str = Form(...),
    relation_type: str = Form(...),
):
    svc, session = _rel_svc(request)
    try:
        await svc.add(
            project_key, local_id,
            to_local_id=to_local_id, relation_type=relation_type,
        )
    finally:
        await session.close()

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return Response(
            status_code=200,
            headers={"HX-Redirect": f"/dashboard/{project_key}/items/{local_id}"},
        )
    return RedirectResponse(
        url=f"/dashboard/{project_key}/items/{local_id}", status_code=303,
    )


@router.post("/{project_key}/relationships/{rel_id}/delete")
async def remove_relationship(
    project_key: str, rel_id: int, request: Request,
):
    svc, session = _rel_svc(request)
    try:
        await svc.remove(rel_id)
    finally:
        await session.close()

    is_htmx = request.headers.get("HX-Request") == "true"
    referer = request.headers.get("HX-Current-URL", f"/dashboard/{project_key}/kanban")
    if is_htmx:
        return Response(
            status_code=200,
            headers={"HX-Redirect": referer},
        )
    return RedirectResponse(url=referer, status_code=303)


# ---------------------------------------------------------------------------
# Chart color helper
# ---------------------------------------------------------------------------

_CHART_STATUS_COLORS = {
    "proposed": "#aeb8af",
    "in_progress": "#0f766e",
    "done": "#15803d",
    "wontfix": "#687076",
}

_CHART_KIND_COLORS = {
    "feature": "#0f766e",
    "bug": "#b42318",
    "improvement": "#15803d",
    "research": "#4d7c0f",
    "breaking": "#b45309",
    "infra": "#687076",
    "note": "#2563eb",
}


def _chart_color(key: str, category: str) -> str:
    if category == "status":
        return _CHART_STATUS_COLORS.get(key, "#6b7280")
    return _CHART_KIND_COLORS.get(key, "#6b7280")
