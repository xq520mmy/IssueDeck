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
from issuedeck.features.demo.seed import seed_demo_project
from issuedeck.features.items.models import Base
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.service import ItemService


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"example": ProjectConfig(
            key="example",
            name="Example",
            kinds={
                "feature": KindConfig(label="Feature", prefix="FEAT"),
                "bug": KindConfig(label="Bug", prefix="BUG"),
                "improvement": KindConfig(label="Improvement", prefix="IMP"),
            },
            statuses={
                "proposed": StatusConfig(label="Proposed"),
                "in_progress": StatusConfig(label="In Progress"),
                "done": StatusConfig(label="Done", terminal=True, requires_ship=True),
                "wontfix": StatusConfig(label="Won't Fix", terminal=True),
            },
            branches=[BranchConfig(key="main", label="Main")],
        )},
    )


@pytest.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s, _registry()
    await engine.dispose()


async def test_seed_demo_project_writes_fake_items(ctx):
    session, registry = ctx
    report = await seed_demo_project(session=session, registry=registry)
    assert report.items_written == 8
    assert report.relationships_written == 3
    assert report.events_written == 3
    assert report.work_sessions_written == 2

    items = await ItemService(ItemRepo(session), registry, session).list_items(
        "example",
        limit=20,
    )
    assert len(items.items) == 8
    assert "Add agent activity timeline" in {item.title for item in items.items}


async def test_seed_demo_refuses_to_overwrite_without_force(ctx):
    session, registry = ctx
    await seed_demo_project(session=session, registry=registry)
    with pytest.raises(ValueError, match="already has"):
        await seed_demo_project(session=session, registry=registry)

    report = await seed_demo_project(
        session=session,
        registry=registry,
        force_reset=True,
    )
    assert report.reset is True
