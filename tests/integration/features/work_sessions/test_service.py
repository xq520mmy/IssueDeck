import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from issuedeck.core.config import (
    BranchConfig,
    ConfigRegistry,
    KindConfig,
    ProjectConfig,
    ServerConfig,
    StatusConfig,
)
from issuedeck.core.errors import InvalidTransition
from issuedeck.features.items.models import Base
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import CreateItemRequest
from issuedeck.features.items.service import ItemService
from issuedeck.features.work_sessions.repo import WorkSessionRepo
from issuedeck.features.work_sessions.schemas import (
    CreateWorkSessionRequest,
    FinishWorkSessionRequest,
    UpdateWorkSessionRequest,
)
from issuedeck.features.work_sessions.service import WorkSessionService


def _registry() -> ConfigRegistry:
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={
            "test": ProjectConfig(
                key="test",
                name="Test",
                kinds={"feature": KindConfig(label="Feature", prefix="FEAT")},
                statuses={
                    "proposed": StatusConfig(label="Proposed"),
                    "in_progress": StatusConfig(label="In Progress"),
                    "done": StatusConfig(label="Done", terminal=True, requires_ship=True),
                },
                branches=[BranchConfig(key="main", label="Main")],
            )
        },
    )


@pytest.fixture
async def services():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        registry = _registry()
        yield (
            ItemService(ItemRepo(s), registry, s),
            WorkSessionService(WorkSessionRepo(s), ItemRepo(s), registry, s),
        )
    await engine.dispose()


async def test_work_session_lifecycle_records_item_events(services):
    items, work_sessions = services
    item = await items.create(
        "test",
        CreateItemRequest(kind="feature", title="Session-aware work"),
    )

    session = await work_sessions.start(
        "test",
        CreateWorkSessionRequest(
            local_id=item.local_id,
            agent_name="codex",
            goal="Implement session tracking.",
            branch="main",
            metadata={"source": "test"},
        ),
    )

    assert session.status == "active"
    assert session.local_id == item.local_id
    assert session.update_count == 1
    assert session.updates[0].update_type == "started"

    session = await work_sessions.update(
        "test",
        session.id,
        UpdateWorkSessionRequest(
            message="Dashboard section is wired.",
            status="paused",
        ),
    )
    assert session.status == "paused"
    assert session.update_count == 2

    session = await work_sessions.finish(
        "test",
        session.id,
        FinishWorkSessionRequest(summary="Shipped the session UI."),
    )
    assert session.status == "completed"
    assert session.ended_at is not None
    assert session.summary == "Shipped the session UI."

    detail = await items.get("test", item.local_id)
    event_types = [event.event_type for event in detail.events]
    assert "work_session_started" in event_types
    assert "work_session_paused" in event_types
    assert "work_session_completed" in event_types

    with pytest.raises(InvalidTransition):
        await work_sessions.update(
            "test",
            session.id,
            UpdateWorkSessionRequest(message="Too late."),
        )


async def test_list_work_sessions_filters_by_status_and_item(services):
    items, work_sessions = services
    item = await items.create("test", CreateItemRequest(kind="feature", title="One"))
    other = await items.create("test", CreateItemRequest(kind="feature", title="Two"))

    active = await work_sessions.start(
        "test",
        CreateWorkSessionRequest(
            local_id=item.local_id,
            agent_name="codex",
            goal="Keep this one open.",
        ),
    )
    done = await work_sessions.start(
        "test",
        CreateWorkSessionRequest(
            local_id=other.local_id,
            agent_name="codex",
            goal="Finish this one.",
        ),
    )
    await work_sessions.finish(
        "test",
        done.id,
        FinishWorkSessionRequest(summary="Done."),
    )

    active_sessions = await work_sessions.list_sessions(
        "test",
        statuses=["active"],
        limit=10,
    )
    assert [session.id for session in active_sessions.sessions] == [active.id]

    item_sessions = await work_sessions.list_sessions(
        "test",
        local_id=other.local_id,
        limit=10,
    )
    assert [session.local_id for session in item_sessions.sessions] == [other.local_id]

