import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from issuedeck.core.config import (
    BranchConfig,
    ConfigRegistry,
    CustomFieldConfig,
    KindConfig,
    ProjectConfig,
    ServerConfig,
    StatusConfig,
)
from issuedeck.core.errors import InvalidCustomField, InvalidKind, ItemNotFound
from issuedeck.features.items.models import Base
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import (
    BulkUpdateItemsRequest,
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


def _make_custom_field_registry() -> ConfigRegistry:
    registry = _make_registry()
    registry._projects["test"].custom_fields = {
        "priority": CustomFieldConfig(
            label="Priority",
            type="select",
            required=True,
            options=["low", "high"],
        ),
        "estimate": CustomFieldConfig(label="Estimate", type="number"),
        "customer_impact": CustomFieldConfig(label="Customer impact", type="checkbox"),
    }
    return registry


@pytest.fixture
async def service():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield ItemService(ItemRepo(s), _make_registry(), s)
    await engine.dispose()


@pytest.fixture
async def custom_field_service():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield ItemService(ItemRepo(s), _make_custom_field_registry(), s)
    await engine.dispose()


class RecordingWebhookDispatcher:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event, item):
        self.events.append((event, item.local_id, item.deleted_at))


@pytest.fixture
async def service_with_webhooks():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    dispatcher = RecordingWebhookDispatcher()
    async with Session() as s:
        yield (
            ItemService(
                ItemRepo(s),
                _make_registry(),
                s,
                webhook_dispatcher=dispatcher,
            ),
            dispatcher,
        )
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


async def test_create_item_persists_custom_fields(custom_field_service):
    summary = await custom_field_service.create(
        "test",
        CreateItemRequest(
            kind="feature",
            title="Custom fields",
            custom_fields={
                "priority": "high",
                "estimate": "3",
                "customer_impact": "on",
            },
        ),
    )

    assert summary.custom_fields == {
        "priority": "high",
        "estimate": 3,
        "customer_impact": True,
    }
    detail = await custom_field_service.get("test", "FEAT-0001")
    assert detail.custom_fields["priority"] == "high"


async def test_update_item_merges_custom_fields(custom_field_service):
    await custom_field_service.create(
        "test",
        CreateItemRequest(
            kind="feature",
            title="Custom fields",
            custom_fields={"priority": "low", "estimate": "1"},
        ),
    )

    await custom_field_service.update(
        "test",
        "FEAT-0001",
        UpdateItemRequest(custom_fields={"estimate": "5"}),
    )

    detail = await custom_field_service.get("test", "FEAT-0001")
    assert detail.custom_fields == {
        "priority": "low",
        "estimate": 5,
        "customer_impact": False,
    }
    assert detail.events[0].metadata["fields"] == ["custom_fields"]


async def test_custom_fields_reject_unknown_or_invalid_values(custom_field_service):
    with pytest.raises(InvalidCustomField, match="missing required"):
        await custom_field_service.create(
            "test",
            CreateItemRequest(kind="feature", title="Missing custom field"),
        )

    with pytest.raises(InvalidCustomField, match="unknown custom field"):
        await custom_field_service.create(
            "test",
            CreateItemRequest(
                kind="feature",
                title="Unknown custom field",
                custom_fields={"priority": "high", "severity": "critical"},
            ),
        )

    with pytest.raises(InvalidCustomField, match="must be one of"):
        await custom_field_service.create(
            "test",
            CreateItemRequest(
                kind="feature",
                title="Bad select",
                custom_fields={"priority": "urgent"},
            ),
        )


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


async def test_bulk_update_changes_status_kind_tags_and_branches(service):
    await service.create("test", CreateItemRequest(kind="feature", title="one", tags=["old"]))
    await service.create("test", CreateItemRequest(kind="feature", title="two", tags=["old"]))

    result = await service.bulk_update(
        "test",
        BulkUpdateItemsRequest(
            local_ids=["FEAT-0001", "FEAT-0002"],
            kind="bug",
            status="in_progress",
            tags=["triaged"],
            tag_mode="replace",
            applies_to=["main"],
        ),
    )

    assert result.updated_count == 2
    assert [(item.local_id, item.kind, item.status, item.tags) for item in result.items] == [
        ("FEAT-0001", "bug", "in_progress", ["triaged"]),
        ("FEAT-0002", "bug", "in_progress", ["triaged"]),
    ]
    detail = await service.get("test", "FEAT-0001")
    assert detail.events[0].event_type == "updated"
    assert detail.events[0].metadata["bulk"] is True
    assert detail.events[0].metadata["fields"] == [
        "kind",
        "status",
        "tags",
        "applies_to",
    ]


async def test_bulk_update_adds_and_removes_tags(service):
    await service.create("test", CreateItemRequest(kind="feature", title="one", tags=["old"]))

    added = await service.bulk_update(
        "test",
        BulkUpdateItemsRequest(local_ids=["FEAT-0001"], tags=["triaged"], tag_mode="add"),
    )
    assert added.items[0].tags == ["old", "triaged"]

    removed = await service.bulk_update(
        "test",
        BulkUpdateItemsRequest(local_ids=["FEAT-0001"], tags=["old"], tag_mode="remove"),
    )
    assert removed.items[0].tags == ["triaged"]


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


async def test_lifecycle_actions_emit_webhooks(service_with_webhooks):
    service, dispatcher = service_with_webhooks

    await service.create("test", CreateItemRequest(kind="feature", title="t"))
    await service.update("test", "FEAT-0001", UpdateItemRequest(title="updated"))
    await service.update("test", "FEAT-0001", UpdateItemRequest())
    await service.ship(
        "test",
        "FEAT-0001",
        ShipItemRequest(branch="main", version="0.1.0"),
    )
    await service.soft_delete("test", "FEAT-0001")
    await service.restore("test", "FEAT-0001")

    assert [event for event, _local_id, _deleted_at in dispatcher.events] == [
        "item.created",
        "item.updated",
        "item.shipped",
        "item.deleted",
        "item.restored",
    ]
    assert all(local_id == "FEAT-0001" for _event, local_id, _deleted_at in dispatcher.events)
    assert dispatcher.events[-2][2] is not None
    assert dispatcher.events[-1][2] is None


async def test_bulk_delete_and_restore_emit_webhooks(service_with_webhooks):
    service, dispatcher = service_with_webhooks

    await service.create("test", CreateItemRequest(kind="feature", title="one"))
    await service.create("test", CreateItemRequest(kind="feature", title="two"))

    deleted = await service.bulk_update(
        "test",
        BulkUpdateItemsRequest(local_ids=["FEAT-0001", "FEAT-0002"], action="delete"),
    )
    assert deleted.updated_count == 2
    assert all(item.deleted_at is not None for item in deleted.items)

    restored = await service.bulk_update(
        "test",
        BulkUpdateItemsRequest(local_ids=["FEAT-0001", "FEAT-0002"], action="restore"),
    )
    assert restored.updated_count == 2
    assert all(item.deleted_at is None for item in restored.items)

    assert [event for event, _local_id, _deleted_at in dispatcher.events] == [
        "item.created",
        "item.created",
        "item.deleted",
        "item.deleted",
        "item.restored",
        "item.restored",
    ]
