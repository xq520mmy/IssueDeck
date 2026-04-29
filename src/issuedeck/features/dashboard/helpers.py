"""Dashboard template helpers — Jinja2 setup, stats aggregation, color maps."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import HTMLResponse

from issuedeck.core.config import ProjectConfig
from issuedeck.features.items.models import Item

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_env: Environment | None = None


def get_jinja_env() -> Environment:
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
            enable_async=False,
        )
        _env.globals["kind_colors"] = KIND_COLORS
        _env.globals["status_colors"] = STATUS_COLORS
    return _env


def render(
    template_name: str,
    request: Request,
    *,
    is_htmx: bool | None = None,
    partial_template: str | None = None,
    status_code: int = 200,
    **ctx,
) -> HTMLResponse:
    """Render a full page or HTMX partial.

    If the request has HX-Request header and partial_template is provided,
    render just the partial. Otherwise render the full page.
    """
    if is_htmx is None:
        is_htmx = request.headers.get("HX-Request") == "true"

    env = get_jinja_env()
    if is_htmx and partial_template:
        tpl = env.get_template(partial_template)
    else:
        tpl = env.get_template(template_name)

    html = tpl.render(request=request, **ctx)
    return HTMLResponse(html, status_code=status_code)


# ---------------------------------------------------------------------------
# Color maps — Tailwind CSS classes
# ---------------------------------------------------------------------------

KIND_COLORS: dict[str, dict[str, str]] = {
    "feature": {
        "bg": "bg-primary-50 dark:bg-primary-950",
        "text": "text-primary-700 dark:text-primary-200",
        "border": "border-primary-600 dark:border-primary-400",
    },
    "bug": {
        "bg": "bg-red-50 dark:bg-red-950/40",
        "text": "text-red-700 dark:text-red-300",
        "border": "border-red-600 dark:border-red-400",
    },
    "improvement": {
        "bg": "bg-green-50 dark:bg-green-950/40",
        "text": "text-green-700 dark:text-green-300",
        "border": "border-green-600 dark:border-green-400",
    },
    "research": {
        "bg": "bg-lime-50 dark:bg-lime-950/30",
        "text": "text-lime-800 dark:text-lime-300",
        "border": "border-lime-600 dark:border-lime-400",
    },
    "breaking": {
        "bg": "bg-ship-50 dark:bg-ship-600/20",
        "text": "text-ship-700 dark:text-ship-100",
        "border": "border-ship-600 dark:border-ship-500",
    },
    "infra": {
        "bg": "bg-gray-100 dark:bg-gray-800",
        "text": "text-gray-700 dark:text-gray-300",
        "border": "border-gray-500 dark:border-gray-400",
    },
    "note": {
        "bg": "bg-sky-50 dark:bg-sky-950/30",
        "text": "text-sky-700 dark:text-sky-300",
        "border": "border-sky-500 dark:border-sky-400",
    },
}
_DEFAULT_KIND_COLOR = {
    "bg": "bg-gray-100 dark:bg-gray-800",
    "text": "text-gray-700 dark:text-gray-300",
    "border": "border-gray-500 dark:border-gray-400",
}

STATUS_COLORS: dict[str, dict[str, str]] = {
    "proposed": {
        "bg": "bg-gray-100 dark:bg-gray-800",
        "text": "text-gray-700 dark:text-gray-300",
        "dot": "bg-gray-400 dark:bg-gray-500",
    },
    "in_progress": {
        "bg": "bg-primary-50 dark:bg-primary-950",
        "text": "text-primary-700 dark:text-primary-200",
        "dot": "bg-primary-600 dark:bg-primary-300",
    },
    "done": {
        "bg": "bg-green-50 dark:bg-green-950/40",
        "text": "text-green-700 dark:text-green-300",
        "dot": "bg-green-600 dark:bg-green-400",
    },
    "wontfix": {
        "bg": "bg-gray-100 dark:bg-gray-800",
        "text": "text-gray-500 dark:text-gray-400",
        "dot": "bg-gray-400 dark:bg-gray-500",
    },
}
_DEFAULT_STATUS_COLOR = {
    "bg": "bg-gray-100 dark:bg-gray-800",
    "text": "text-gray-600 dark:text-gray-400",
    "dot": "bg-gray-400 dark:bg-gray-500",
}

STATUS_LABELS: dict[str, str] = {
    "proposed": "Proposed",
    "in_progress": "In progress",
    "done": "Done",
    "wontfix": "Won't fix",
}

KIND_LABELS: dict[str, str] = {
    "feature": "Feature",
    "bug": "Bug",
    "improvement": "Improvement",
    "research": "Research",
    "breaking": "Breaking change",
    "infra": "Infrastructure",
    "note": "Note",
}

RELATION_LABELS: dict[str, str] = {
    "blocks": "Blocks",
    "blocked_by": "Blocked by",
    "related_to": "Related",
}


def kind_color(kind: str) -> dict[str, str]:
    return KIND_COLORS.get(kind, _DEFAULT_KIND_COLOR)


def status_color(status: str) -> dict[str, str]:
    return STATUS_COLORS.get(status, _DEFAULT_STATUS_COLOR)


def kind_label(kind: str, project: ProjectConfig | None = None) -> str:
    if project and kind in project.kinds:
        return project.kinds[kind].label
    return KIND_LABELS.get(kind, kind)


def status_label(status: str, project: ProjectConfig | None = None) -> str:
    if project and status in project.statuses:
        return project.statuses[status].label
    return STATUS_LABELS.get(status, status)


# ---------------------------------------------------------------------------
# Stats aggregation
# ---------------------------------------------------------------------------

async def count_by_field(
    session: AsyncSession, project_key: str, field: str,
) -> dict[str, int]:
    """Count non-deleted items grouped by a field (status or kind)."""
    col = getattr(Item, field)
    stmt = (
        select(col, func.count())
        .where(Item.project_key == project_key, Item.deleted_at.is_(None))
        .group_by(col)
    )
    rows = (await session.execute(stmt)).all()
    return {row[0]: row[1] for row in rows}


async def total_count(session: AsyncSession, project_key: str) -> int:
    stmt = (
        select(func.count())
        .select_from(Item)
        .where(Item.project_key == project_key, Item.deleted_at.is_(None))
    )
    return (await session.execute(stmt)).scalar() or 0


async def all_tags(session: AsyncSession, project_key: str) -> list[str]:
    """Get all unique tags for a project."""
    from issuedeck.features.items.models import ItemTag
    stmt = (
        select(ItemTag.tag)
        .join(Item, ItemTag.item_pk == Item.pk)
        .where(Item.project_key == project_key, Item.deleted_at.is_(None))
        .distinct()
        .order_by(ItemTag.tag)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)
