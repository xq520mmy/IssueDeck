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
from issuedeck.features.items.models import Base
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import CreateItemRequest
from issuedeck.features.items.service import ItemService
from issuedeck.features.relationships.repo import RelationshipRepo
from issuedeck.features.relationships.service import RelationshipService


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"test": ProjectConfig(
            key="test", name="Test",
            kinds={
                "feature": KindConfig(label="Feature", prefix="FEAT"),
                "bug": KindConfig(label="Bug", prefix="BUG"),
            },
            statuses={"proposed": StatusConfig(label="P")},
            branches=[BranchConfig(key="main", label="Main")],
        )},
    )


@pytest.fixture
async def service():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        svc = ItemService(ItemRepo(s), _registry(), s)
        for i in range(5):
            await svc.create("test", CreateItemRequest(
                kind="feature" if i % 2 == 0 else "bug",
                title=f"t{i}", tags=["hot"] if i == 0 else [],
            ))
        yield svc
    await engine.dispose()


async def test_list_returns_all(service):
    r = await service.list_items("test")
    assert len(r.items) == 5
    assert r.next_cursor is None


async def test_list_filters_by_kind(service):
    r = await service.list_items("test", kinds=["bug"])
    assert {i.kind for i in r.items} == {"bug"}
    assert len(r.items) == 2


async def test_list_filters_by_tag(service):
    r = await service.list_items("test", tags=["hot"])
    assert len(r.items) == 1


async def test_list_pagination_cursor_roundtrip(service):
    page1 = await service.list_items("test", limit=2)
    assert len(page1.items) == 2
    assert page1.next_cursor is not None
    page2 = await service.list_items("test", limit=2, after=page1.next_cursor)
    assert len(page2.items) == 2
    ids1 = {i.local_id for i in page1.items}
    ids2 = {i.local_id for i in page2.items}
    assert ids1.isdisjoint(ids2)


async def test_list_filters_by_relationship_type(service):
    rels = RelationshipService(
        RelationshipRepo(service._s), ItemRepo(service._s),
        service._registry, service._s,
    )
    await rels.add(
        "test",
        "FEAT-0001",
        to_local_id="BUG-0001",
        relation_type="blocks",
    )

    blocked = await service.list_items(
        "test",
        relationship_types=["blocked_by"],
    )
    assert [i.local_id for i in blocked.items] == ["BUG-0001"]


async def test_list_only_deleted(service):
    await service.soft_delete("test", "FEAT-0001")
    deleted = await service.list_items("test", only_deleted=True)
    assert [i.local_id for i in deleted.items] == ["FEAT-0001"]
