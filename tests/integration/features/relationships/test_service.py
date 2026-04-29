import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from issuedeck.core.config import (
    ConfigRegistry,
    KindConfig,
    ProjectConfig,
    ServerConfig,
    StatusConfig,
)
from issuedeck.core.errors import RelationshipDuplicate, RelationshipSelfLoop
from issuedeck.features.items.models import Base, ItemRelationship
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import CreateItemRequest
from issuedeck.features.items.service import ItemService
from issuedeck.features.relationships.repo import RelationshipRepo
from issuedeck.features.relationships.service import RelationshipService


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"p": ProjectConfig(
            key="p", name="P",
            kinds={"feature": KindConfig(label="Feature", prefix="FEAT")},
            statuses={"proposed": StatusConfig(label="P")},
        )},
    )


@pytest.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        reg = _registry()
        items = ItemService(ItemRepo(s), reg, s)
        await items.create("p", CreateItemRequest(kind="feature", title="A"))
        await items.create("p", CreateItemRequest(kind="feature", title="B"))
        rels = RelationshipService(RelationshipRepo(s), ItemRepo(s), reg, s)
        yield items, rels, s
    await engine.dispose()


async def test_add_blocks_creates_two_rows(ctx):
    _, rels, session = ctx
    await rels.add("p", "FEAT-0001", to_local_id="FEAT-0002", relation_type="blocks")
    rows = (await session.execute(select(ItemRelationship))).scalars().all()
    assert len(rows) == 2
    assert any(r.relation_type == "blocks" for r in rows)
    assert any(r.relation_type == "blocked_by" for r in rows)


async def test_self_loop_rejected(ctx):
    _, rels, _ = ctx
    with pytest.raises(RelationshipSelfLoop):
        await rels.add("p", "FEAT-0001", to_local_id="FEAT-0001",
                       relation_type="blocks")


async def test_duplicate_rejected(ctx):
    _, rels, _ = ctx
    await rels.add("p", "FEAT-0001", to_local_id="FEAT-0002",
                   relation_type="blocks")
    with pytest.raises(RelationshipDuplicate):
        await rels.add("p", "FEAT-0001", to_local_id="FEAT-0002",
                       relation_type="blocks")


async def test_related_to_is_symmetric_and_deduped(ctx):
    _, rels, session = ctx
    await rels.add("p", "FEAT-0001", to_local_id="FEAT-0002",
                   relation_type="related_to")
    rows = (await session.execute(select(ItemRelationship))).scalars().all()
    assert len(rows) == 2
    assert all(r.relation_type == "related_to" for r in rows)


async def test_remove_deletes_both_sides(ctx):
    _, rels, session = ctx
    rel = await rels.add(
        "p", "FEAT-0001", to_local_id="FEAT-0002", relation_type="blocks",
    )
    await rels.remove(rel.rel_id)
    rows = (await session.execute(select(ItemRelationship))).scalars().all()
    assert len(rows) == 0
