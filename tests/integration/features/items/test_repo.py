import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from issuedeck.features.items.models import Base
from issuedeck.features.items.repo import ItemRepo


@pytest.fixture
async def repo():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield ItemRepo(s)
    await engine.dispose()


async def test_next_local_id_first(repo):
    nid = await repo.next_local_id("p", kind="feature", prefix="FEAT", digits=4)
    assert nid == "FEAT-0001"


async def test_next_local_id_after_existing(repo):
    await repo.insert_item(
        project_key="p", local_id="FEAT-0001", kind="feature",
        status="proposed", title="x", body="", tags=[], applies_to=[],
    )
    await repo.insert_item(
        project_key="p", local_id="FEAT-0003", kind="feature",
        status="proposed", title="x", body="", tags=[], applies_to=[],
    )
    nid = await repo.next_local_id("p", kind="feature", prefix="FEAT", digits=4)
    assert nid == "FEAT-0004"


async def test_next_local_id_ignores_other_projects(repo):
    await repo.insert_item(
        project_key="other", local_id="FEAT-9999", kind="feature",
        status="proposed", title="x", body="", tags=[], applies_to=[],
    )
    nid = await repo.next_local_id("p", kind="feature", prefix="FEAT", digits=4)
    assert nid == "FEAT-0001"


async def test_load_by_local_id(repo):
    item = await repo.insert_item(
        project_key="p", local_id="FEAT-0001", kind="feature",
        status="proposed", title="Hello", body="body",
        tags=["a", "b"], applies_to=["v3"],
    )
    assert item.pk is not None
    loaded = await repo.get_by_local_id("p", "FEAT-0001")
    assert loaded is not None
    assert loaded.title == "Hello"


async def test_add_and_list_events(repo):
    item = await repo.insert_item(
        project_key="p", local_id="FEAT-0001", kind="feature",
        status="proposed", title="Hello", body="body",
        tags=[], applies_to=[],
    )
    await repo.add_event(
        item_pk=item.pk,
        event_type="comment",
        actor_type="agent",
        actor_name="codex",
        body="Captured the next implementation step.",
        metadata_json='{"phase":"plan"}',
        created_at="2026-04-28T00:00:00+00:00",
    )
    events = await repo.list_events(item.pk)
    assert len(events) == 1
    assert events[0].actor_name == "codex"
    assert events[0].metadata_json == '{"phase":"plan"}'


async def test_get_by_local_id_missing_returns_none(repo):
    assert await repo.get_by_local_id("p", "FEAT-9999") is None


async def test_soft_delete_and_restore(repo):
    item = await repo.insert_item(
        project_key="p", local_id="FEAT-0001", kind="feature",
        status="proposed", title="x", body="", tags=[], applies_to=[],
    )
    await repo.soft_delete(item.pk, deleted_at="2026-04-11T00:00:00+00:00")
    reloaded = await repo.get_by_local_id("p", "FEAT-0001", include_deleted=True)
    assert reloaded.deleted_at == "2026-04-11T00:00:00+00:00"
    assert await repo.get_by_local_id("p", "FEAT-0001") is None

    await repo.restore(item.pk)
    assert await repo.get_by_local_id("p", "FEAT-0001") is not None
