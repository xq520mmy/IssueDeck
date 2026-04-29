from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from issuedeck.core.config import (
    BranchConfig,
    ConfigRegistry,
    KindConfig,
    ProjectConfig,
    ServerConfig,
    StatusConfig,
)
from issuedeck.features.items.models import Base, Item, ShipCommit, ShipRecord
from issuedeck.features.migrate.frontmatter import migrate_frontmatter_bundle

FIX_ROOT = Path(__file__).parent / "fixtures"


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"sample": ProjectConfig(
            key="sample", name="Sample Project",
            kinds={
                "feature": KindConfig(label="Feature", prefix="FEAT"),
                "bug": KindConfig(label="Bug", prefix="BUG"),
            },
            statuses={
                "proposed": StatusConfig(label="P"),
                "done": StatusConfig(label="D", terminal=True, requires_ship=True),
            },
            branches=[
                BranchConfig(key="v3", label="v3"),
                BranchConfig(key="v2", label="v2"),
            ],
        )},
    )


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


async def test_dry_run_does_not_write(session):
    report = await migrate_frontmatter_bundle(
        source_dir=FIX_ROOT, project_key="sample",
        registry=_registry(), db=session, dry_run=True,
    )
    assert report.items_planned == 2
    n = (await session.execute(select(Item))).scalars().all()
    assert len(n) == 0


async def test_full_migration_writes_all(session):
    report = await migrate_frontmatter_bundle(
        source_dir=FIX_ROOT, project_key="sample",
        registry=_registry(), db=session, dry_run=False,
    )
    assert report.items_written == 2

    items = (await session.execute(select(Item).order_by(Item.local_id))).scalars().all()
    assert [i.local_id for i in items] == ["FEAT-0001", "FEAT-0002"]

    ship = (await session.execute(select(ShipRecord))).scalars().all()
    assert len(ship) == 1
    assert ship[0].version == "0.4.2"

    commits = (await session.execute(
        select(ShipCommit).order_by(ShipCommit.position)
    )).scalars().all()
    assert [c.sha for c in commits] == ["abc123", "def456"]


async def test_rerun_without_force_fails(session):
    await migrate_frontmatter_bundle(
        source_dir=FIX_ROOT, project_key="sample",
        registry=_registry(), db=session, dry_run=False,
    )
    from issuedeck.features.migrate.frontmatter import MigrationError
    with pytest.raises(MigrationError):
        await migrate_frontmatter_bundle(
            source_dir=FIX_ROOT, project_key="sample",
            registry=_registry(), db=session, dry_run=False,
        )
