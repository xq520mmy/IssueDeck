"""Seed a fake project with demo tracker data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from issuedeck.core.config import ConfigRegistry
from issuedeck.features.items.models import (
    Item,
    ItemApplyTo,
    ItemEvent,
    ItemExternalLink,
    ItemRelationship,
    ItemTag,
    ShipCommit,
    ShipRecord,
    WorkSession,
    WorkSessionUpdate,
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
from issuedeck.features.work_sessions.repo import WorkSessionRepo
from issuedeck.features.work_sessions.schemas import (
    CreateWorkSessionRequest,
    FinishWorkSessionRequest,
    UpdateWorkSessionRequest,
)
from issuedeck.features.work_sessions.service import WorkSessionService


@dataclass(frozen=True)
class DemoSeedReport:
    project_key: str
    items_written: int
    relationships_written: int
    events_written: int
    ship_records_written: int
    work_sessions_written: int
    reset: bool


async def seed_demo_project(
    *,
    session: AsyncSession,
    registry: ConfigRegistry,
    project_key: str = "example",
    force_reset: bool = False,
) -> DemoSeedReport:
    """Populate a project with fake data that is safe for screenshots and docs."""
    registry.project(project_key)

    existing = await _project_item_count(session, project_key)
    if existing and not force_reset:
        raise ValueError(
            f"project '{project_key}' already has {existing} items; "
            "rerun with force_reset=True to replace them"
        )
    if existing:
        await _reset_project(session, project_key)

    items = ItemService(ItemRepo(session), registry, session)
    rels = RelationshipService(
        RelationshipRepo(session), ItemRepo(session), registry, session,
    )
    work_sessions = WorkSessionService(
        WorkSessionRepo(session), ItemRepo(session), registry, session,
    )

    created: dict[str, str] = {}
    for spec in _DEMO_ITEMS:
        summary = await items.create(
            project_key,
            CreateItemRequest(
                kind=spec["kind"],
                title=spec["title"],
                body=spec["body"],
                tags=spec["tags"],
                applies_to=["main"],
                external_links=spec.get("external_links", []),
            ),
        )
        created[spec["slug"]] = summary.local_id
        if spec.get("status") and spec["status"] != "proposed":
            await items.update(
                project_key,
                summary.local_id,
                UpdateItemRequest(status=spec["status"]),
            )

    await items.ship(
        project_key,
        created["branch-field-bug"],
        ShipItemRequest(
            branch="main",
            version="v0.2.0",
            commits=["8f2a1c4", "b7d9210"],
        ),
    )
    await items.ship(
        project_key,
        created["mobile-sidebar"],
        ShipItemRequest(
            branch="main",
            version="v0.3.0",
            commits=["4ad31ef"],
        ),
    )

    relationships = [
        ("demo-seed", "docs-quickstart", "blocked_by"),
        ("github-import", "work-queues", "related_to"),
        ("i18n-dashboard", "demo-seed", "related_to"),
    ]
    for source, target, rel_type in relationships:
        await rels.add(
            project_key,
            created[source],
            to_local_id=created[target],
            relation_type=rel_type,
        )

    event_count = 0
    for slug, body in _DEMO_EVENTS:
        await items.add_event(
            project_key,
            created[slug],
            CreateItemEventRequest(
                event_type="comment",
                actor_type="agent",
                actor_name="codex",
                body=body,
                metadata={"demo": True},
            ),
        )
        event_count += 1

    active_session = await work_sessions.start(
        project_key,
        CreateWorkSessionRequest(
            local_id=created["agent-timeline"],
            agent_name="codex",
            goal="Wire agent work sessions into REST, MCP, and the dashboard.",
            branch="main",
            metadata={"demo": True},
        ),
    )
    await work_sessions.update(
        project_key,
        active_session.id,
        UpdateWorkSessionRequest(
            message="Dashboard overview now shows the active agent session.",
            metadata={"demo": True},
        ),
    )
    research_session = await work_sessions.start(
        project_key,
        CreateWorkSessionRequest(
            local_id=created["github-import"],
            agent_name="openclaw",
            goal="Compare GitHub issue import edge cases before implementation.",
            branch="main",
            metadata={"demo": True},
        ),
    )
    await work_sessions.finish(
        project_key,
        research_session.id,
        FinishWorkSessionRequest(
            summary="Documented one-way import as the first safe scope.",
            metadata={"demo": True},
        ),
    )

    return DemoSeedReport(
        project_key=project_key,
        items_written=len(created),
        relationships_written=len(relationships),
        events_written=event_count,
        ship_records_written=2,
        work_sessions_written=2,
        reset=bool(existing),
    )


async def _project_item_count(session: AsyncSession, project_key: str) -> int:
    stmt = select(func.count()).select_from(Item).where(Item.project_key == project_key)
    return (await session.execute(stmt)).scalar() or 0


async def _reset_project(session: AsyncSession, project_key: str) -> None:
    pks = list((await session.execute(
        select(Item.pk).where(Item.project_key == project_key)
    )).scalars().all())
    if not pks:
        return

    ship_record_ids = select(ShipRecord.id).where(ShipRecord.item_pk.in_(pks))
    work_session_ids = select(WorkSession.id).where(WorkSession.project_key == project_key)
    await session.execute(delete(WorkSessionUpdate).where(
        WorkSessionUpdate.session_id.in_(work_session_ids)
    ))
    await session.execute(delete(WorkSession).where(WorkSession.project_key == project_key))
    await session.execute(delete(ShipCommit).where(
        ShipCommit.ship_record_id.in_(ship_record_ids)
    ))
    await session.execute(delete(ShipRecord).where(ShipRecord.item_pk.in_(pks)))
    await session.execute(delete(ItemRelationship).where(
        ItemRelationship.from_item_pk.in_(pks)
        | ItemRelationship.to_item_pk.in_(pks)
    ))
    await session.execute(delete(ItemEvent).where(ItemEvent.item_pk.in_(pks)))
    await session.execute(delete(ItemExternalLink).where(ItemExternalLink.item_pk.in_(pks)))
    await session.execute(delete(ItemApplyTo).where(ItemApplyTo.item_pk.in_(pks)))
    await session.execute(delete(ItemTag).where(ItemTag.item_pk.in_(pks)))
    await session.execute(delete(Item).where(Item.pk.in_(pks)))
    await session.commit()


_DEMO_ITEMS = [
    {
        "slug": "agent-timeline",
        "kind": "feature",
        "status": "in_progress",
        "title": "Add agent activity timeline",
        "body": (
            "Capture decisions, handoffs, and verification notes directly on "
            "each work item so humans and coding agents share one ledger."
        ),
        "tags": ["agent", "ledger", "ux"],
    },
    {
        "slug": "work-queues",
        "kind": "feature",
        "status": "in_progress",
        "title": "Ship built-in work queues",
        "body": (
            "Add Recent, Backlog, Active, Blocked, Ready to ship, Done, and "
            "Deleted views to make daily triage fast."
        ),
        "tags": ["dashboard", "workflow"],
    },
    {
        "slug": "branch-field-bug",
        "kind": "bug",
        "status": "proposed",
        "title": "Fix ship modal branch field",
        "body": "The dashboard ship form should submit branch, not branch_key.",
        "tags": ["dashboard", "release"],
    },
    {
        "slug": "demo-seed",
        "kind": "improvement",
        "status": "proposed",
        "title": "Create fake demo data for README screenshots",
        "body": (
            "Provide a repeatable demo seed so public docs never expose private "
            "project names or internal work."
        ),
        "tags": ["docs", "demo"],
    },
    {
        "slug": "docs-quickstart",
        "kind": "improvement",
        "status": "proposed",
        "title": "Polish Docker quickstart",
        "body": "Make the first five minutes obvious for a new self-hosted install.",
        "tags": ["docs", "docker"],
    },
    {
        "slug": "github-import",
        "kind": "feature",
        "status": "proposed",
        "title": "Explore GitHub issue import",
        "body": "Research a one-way import path without committing to sync semantics.",
        "tags": ["integration", "research"],
        "external_links": [
            {
                "link_type": "github_issue",
                "label": "GitHub issue #42",
                "url": "https://github.com/example/issuedeck-demo/issues/42",
            }
        ],
    },
    {
        "slug": "mobile-sidebar",
        "kind": "bug",
        "status": "proposed",
        "title": "Fix mobile sidebar clipping",
        "body": "The mobile drawer should fully leave the viewport when closed.",
        "tags": ["mobile", "ui"],
    },
    {
        "slug": "i18n-dashboard",
        "kind": "improvement",
        "status": "proposed",
        "title": "Add language switcher foundation",
        "body": "Start with dashboard chrome and documentation language links.",
        "tags": ["i18n", "oss"],
    },
]

_DEMO_EVENTS = [
    (
        "agent-timeline",
        "Implemented the event model and added REST/MCP append support.",
    ),
    (
        "work-queues",
        "Verified queue navigation in the dashboard with a browser smoke test.",
    ),
    (
        "demo-seed",
        "Use this project for README screenshots and release demos.",
    ),
]
