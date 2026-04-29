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
from issuedeck.core.errors import InvalidKind, ItemNotFound
from issuedeck.features.items.models import Base
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import (
    CreateItemEventRequest,
    CreateItemRequest,
    ShipItemRequest,
    UpdateItemRequest,
)
from issuedeck.features.items.service import ItemService


def _make_registry() -> ConfigRegistry:
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={
            "test": ProjectConfig(
                key="test", name="Test",
                kinds={
                    "feature": KindConfig(label="Feature", prefix="FEAT"),
                    "bug": KindConfig(label="Bug", prefix="BUG"),
                },
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
async def service():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield ItemService(ItemRepo(s), _make_registry(), s)
    await engine.dispose()


async def test_create_item_assigns_local_id(service):
    summary = await service.create(
        "test", CreateItemRequest(kind="feature", title="Hello"),
    )
    assert summary.local_id == "FEAT-0001"
    assert summary.status == "proposed"
    detail = await service.get("test", "FEAT-0001")
    assert detail.events[0].event_type == "created"


async def test_create_item_persists_external_links(service):
    await service.create(
        "test",
        CreateItemRequest(
            kind="feature",
            title="Link back to GitHub",
            external_links=[
                {
                    "link_type": "github_pr",
                    "label": "PR #12",
                    "url": "https://github.com/example/repo/pull/12",
                }
            ],
        ),
    )

    detail = await service.get("test", "FEAT-0001")
    assert detail.external_links[0].link_type == "github_pr"
    assert detail.external_links[0].label == "PR #12"
    assert detail.external_links[0].url == "https://github.com/example/repo/pull/12"


async def test_create_item_rejects_unknown_kind(service):
    with pytest.raises(InvalidKind):
        await service.create("test", CreateItemRequest(kind="spike", title="x"))


async def test_create_item_sequential_ids(service):
    for i in range(3):
        s = await service.create("test", CreateItemRequest(kind="feature", title=f"t{i}"))
    assert s.local_id == "FEAT-0003"


async def test_get_item_missing(service):
    with pytest.raises(ItemNotFound):
        await service.get("test", "FEAT-9999")


async def test_update_item_append_body(service):
    await service.create("test", CreateItemRequest(kind="feature", title="t", body="first"))
    await service.update(
        "test", "FEAT-0001", UpdateItemRequest(append_body="second"),
    )
    full = await service.get("test", "FEAT-0001")
    assert full.body == "first\nsecond"
    assert full.events[0].event_type == "updated"
    assert full.events[0].metadata["fields"] == ["body"]


async def test_update_item_replaces_external_links(service):
    await service.create(
        "test",
        CreateItemRequest(
            kind="feature",
            title="t",
            external_links=[
                {
                    "link_type": "github_issue",
                    "label": "Issue #1",
                    "url": "https://github.com/example/repo/issues/1",
                }
            ],
        ),
    )
    await service.update(
        "test",
        "FEAT-0001",
        UpdateItemRequest(
            external_links=[
                {
                    "link_type": "github_commit",
                    "label": "abc123",
                    "url": "https://github.com/example/repo/commit/abc123",
                }
            ],
        ),
    )

    full = await service.get("test", "FEAT-0001")
    assert [link.link_type for link in full.external_links] == ["github_commit"]
    assert full.events[0].metadata["fields"] == ["external_links"]


async def test_add_event_appends_comment(service):
    await service.create("test", CreateItemRequest(kind="feature", title="t"))
    event = await service.add_event(
        "test",
        "FEAT-0001",
        CreateItemEventRequest(
            event_type="comment",
            actor_type="agent",
            actor_name="codex",
            body="Next step is activity timeline UI.",
            metadata={"source": "test"},
        ),
    )
    assert event.actor_name == "codex"
    assert event.metadata == {"source": "test"}

    full = await service.get("test", "FEAT-0001")
    assert full.events[0].body == "Next step is activity timeline UI."


async def test_ship_item_binds_version_and_marks_done(service):
    await service.create("test", CreateItemRequest(kind="feature", title="t"))
    summary = await service.ship(
        "test", "FEAT-0001",
        ShipItemRequest(branch="main", version="0.1.0", commits=["abc"]),
    )
    assert summary.status == "done"
    detail = await service.get("test", "FEAT-0001")
    assert detail.ship_records[0].version == "0.1.0"
    assert detail.ship_records[0].commits == ["abc"]


async def test_ship_item_second_ship_preserves_first(service):
    registry = _make_registry()
    registry._projects["test"].branches.append(BranchConfig(key="v2", label="v2"))
    service._registry = registry

    await service.create("test", CreateItemRequest(kind="feature", title="t"))
    await service.ship("test", "FEAT-0001",
                       ShipItemRequest(branch="main", version="0.1.0"))
    await service.ship("test", "FEAT-0001",
                       ShipItemRequest(branch="v2", version="0.0.9"))
    detail = await service.get("test", "FEAT-0001")
    versions = {r.branch_key: r.version for r in detail.ship_records}
    assert versions == {"main": "0.1.0", "v2": "0.0.9"}


async def test_soft_delete_hides_from_get(service):
    await service.create("test", CreateItemRequest(kind="feature", title="t"))
    await service.soft_delete("test", "FEAT-0001", reason="wontfix")
    with pytest.raises(ItemNotFound):
        await service.get("test", "FEAT-0001")
    restored = await service.get("test", "FEAT-0001", include_deleted=True)
    assert restored.deleted_at is not None
