import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from issuedeck.features.items.models import (
    Base,
    Item,
    ItemApplyTo,
    ItemEvent,
    ItemRelationship,
    ItemTag,
    ShipCommit,
    ShipRecord,
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


async def test_insert_minimal_item(session):
    item = Item(
        project_key="test",
        local_id="FEAT-0001",
        kind="feature",
        status="proposed",
        title="Hello",
        body="",
        created_at="2026-04-11T00:00:00+00:00",
        updated_at="2026-04-11T00:00:00+00:00",
    )
    session.add(item)
    await session.commit()
    assert item.pk is not None


async def test_unique_local_id_per_project(session):
    for local_id in ("FEAT-0001", "FEAT-0001"):
        session.add(Item(
            project_key="test", local_id=local_id,
            kind="feature", status="proposed", title="x",
            created_at="t", updated_at="t",
        ))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_same_local_id_different_projects_ok(session):
    session.add_all([
        Item(project_key="a", local_id="FEAT-0001", kind="feature",
             status="proposed", title="a", created_at="t", updated_at="t"),
        Item(project_key="b", local_id="FEAT-0001", kind="feature",
             status="proposed", title="b", created_at="t", updated_at="t"),
    ])
    await session.commit()
    items = (await session.execute(select(Item))).scalars().all()
    assert len(items) == 2


async def test_ship_record_with_commits(session):
    item = Item(project_key="p", local_id="FEAT-0001", kind="feature",
                status="done", title="x", created_at="t", updated_at="t")
    session.add(item)
    await session.flush()

    sr = ShipRecord(item_pk=item.pk, branch_key="v3", version="0.4.2",
                    shipped_at="2026-04-11T00:00:00+00:00")
    session.add(sr)
    await session.flush()

    session.add_all([
        ShipCommit(ship_record_id=sr.id, sha="abc123", position=0),
        ShipCommit(ship_record_id=sr.id, sha="def456", position=1),
    ])
    await session.commit()

    fetched = (
        await session.execute(select(ShipCommit).order_by(ShipCommit.position))
    ).scalars().all()
    assert [c.sha for c in fetched] == ["abc123", "def456"]


async def test_tag_and_apply_to_and_relationship(session):
    a = Item(project_key="p", local_id="FEAT-0001", kind="feature",
             status="proposed", title="a", created_at="t", updated_at="t")
    b = Item(project_key="p", local_id="FEAT-0002", kind="feature",
             status="proposed", title="b", created_at="t", updated_at="t")
    session.add_all([a, b])
    await session.flush()

    session.add_all([
        ItemTag(item_pk=a.pk, tag="critical"),
        ItemApplyTo(item_pk=a.pk, branch_key="v3"),
        ItemRelationship(from_item_pk=a.pk, to_item_pk=b.pk,
                         relation_type="blocks", created_at="t"),
        ItemRelationship(from_item_pk=b.pk, to_item_pk=a.pk,
                         relation_type="blocked_by", created_at="t"),
    ])
    await session.commit()


async def test_item_event_persists(session):
    item = Item(project_key="p", local_id="FEAT-0001", kind="feature",
                status="proposed", title="a", created_at="t", updated_at="t")
    session.add(item)
    await session.flush()

    session.add(ItemEvent(
        item_pk=item.pk,
        event_type="comment",
        actor_type="agent",
        actor_name="codex",
        body="Investigated implementation path.",
        metadata_json='{"source":"test"}',
        created_at="t",
    ))
    await session.commit()

    events = (await session.execute(select(ItemEvent))).scalars().all()
    assert events[0].body == "Investigated implementation path."
