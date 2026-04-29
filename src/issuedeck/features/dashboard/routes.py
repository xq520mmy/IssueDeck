"""Dashboard routes — server-rendered Jinja2 pages with HTMX interactions."""

from __future__ import annotations

import hmac
import json
import re

from fastapi import APIRouter, Form, Query, Request, Response
from fastapi.responses import RedirectResponse

from issuedeck.core.auth import (
    DASHBOARD_SESSION_COOKIE,
    DASHBOARD_SESSION_MAX_AGE_SECONDS,
    make_dashboard_session_cookie,
)
from issuedeck.core.config import ProjectConfig
from issuedeck.core.errors import ConfigError
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
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import (
    CreateItemEventRequest,
    CreateItemRequest,
    ShipItemRequest,
    UpdateItemRequest,
)
from issuedeck.features.items.service import ItemService
from issuedeck.features.relationships.repo import RelationshipRepo
from issuedeck.features.relationships.service import RelationshipService
from issuedeck.features.search.repo import SearchRepo
from issuedeck.features.search.service import SearchService

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
RELATION_TYPE_FORM = Form([])
NEXT_QUERY = Query("/dashboard/")
NEXT_FORM = Form("/dashboard/")

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


def _item_svc(request: Request):
    session = request.app.state.session_factory()
    registry = request.app.state.registry
    return ItemService(ItemRepo(session), registry, session), session


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


def _default_project_toml(*, key: str, name: str, description: str) -> str:
    escaped_name = name.replace('"', '\\"')
    escaped_description = description.replace('"', '\\"')
    return f'''key = "{key}"
name = "{escaped_name}"
description = "{escaped_description}"

[kinds.feature]
label = "Feature"
prefix = "FEAT"

[kinds.bug]
label = "Bug"
prefix = "BUG"

[kinds.improvement]
label = "Improvement"
prefix = "IMP"

[statuses.proposed]
label = "Proposed"

[statuses.in_progress]
label = "In Progress"

[statuses.done]
label = "Done"
terminal = true
requires_ship = true

[statuses.wontfix]
label = "Won't Fix"
terminal = true

[[branches]]
key = "main"
label = "Main"

[id_format]
digits = 4
'''


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
    return RedirectResponse(
        url=f"/dashboard/{projects[0].key}", status_code=302,
    )


# ---------------------------------------------------------------------------
# Project creation
# ---------------------------------------------------------------------------

@router.get("/projects-new")
async def create_project_form(request: Request):
    return render(
        "pages/project_form.html", request,
        **_ctx(request),
        active_page="new_project",
        error=None,
    )


@router.post("/projects-new")
async def create_project_submit(
    request: Request,
    key: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
):
    registry = request.app.state.registry
    key = key.strip().lower()
    name = name.strip()
    description = description.strip()
    t = make_translator(language_from_request(request))

    error = None
    if not PROJECT_KEY_RE.fullmatch(key):
        error = t("project_form.error.invalid_key")
    elif not name:
        error = t("project_form.error.name_required")
    elif key in {p.key for p in registry.all_projects()}:
        error = t("project_form.error.exists", key=key)

    if error:
        return render(
            "pages/project_form.html", request,
            **_ctx(request),
            active_page="new_project",
            error=error,
            form={"key": key, "name": name, "description": description},
            status_code=422,
        )

    path = registry.server.projects_dir / f"{key}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return render(
            "pages/project_form.html", request,
            **_ctx(request),
            active_page="new_project",
            error=t("project_form.error.exists_on_disk", name=path.name),
            form={"key": key, "name": name, "description": description},
            status_code=409,
        )

    path.write_text(
        _default_project_toml(key=key, name=name, description=description),
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
            active_page="new_project",
            error=str(exc),
            form={"key": key, "name": name, "description": description},
            status_code=422,
        )

    return RedirectResponse(url=f"/dashboard/{key}", status_code=303)


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
        status_chart_json=json.dumps(status_chart),
        kind_chart_json=json.dumps(kind_chart),
        active_page="overview",
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
):
    registry = request.app.state.registry
    project = registry.project(project_key)
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
        filter_include_deleted=effective_include_deleted,
        active_page="list",
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
    registry.project(project_key)
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

    return render(
        "pages/item_detail.html", request,
        **_ctx(request, project_key),
        item=item,
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
