import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
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
from issuedeck.core.errors import install_error_handlers
from issuedeck.features.dashboard.routes import router as dashboard_router
from issuedeck.features.items.models import Base
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import CreateItemRequest
from issuedeck.features.items.service import ItemService


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"test": ProjectConfig(
            key="test",
            name="Test",
            kinds={
                "feature": KindConfig(label="Feature", prefix="FEAT"),
                "bug": KindConfig(label="Bug", prefix="BUG"),
            },
            statuses={
                "proposed": StatusConfig(label="Proposed"),
                "in_progress": StatusConfig(label="In Progress"),
                "done": StatusConfig(label="Done", terminal=True, requires_ship=True),
            },
            branches=[
                BranchConfig(key="main", label="Main"),
                BranchConfig(key="next", label="Next"),
            ],
            custom_fields={
                "priority": CustomFieldConfig(
                    label="Priority",
                    type="select",
                    options=["low", "high"],
                ),
            },
        )},
    )


@pytest.fixture
async def dashboard_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    registry = _registry()
    async with Session() as session:
        svc = ItemService(ItemRepo(session), registry, session)
        await svc.create("test", CreateItemRequest(kind="feature", title="one"))
        await svc.create("test", CreateItemRequest(kind="feature", title="two"))

    app = FastAPI()
    app.state.registry = registry
    app.state.session_factory = Session
    install_error_handlers(app)
    app.include_router(dashboard_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, Session
    await engine.dispose()


async def test_list_page_renders_bulk_triage_controls(dashboard_client):
    client, _Session = dashboard_client

    response = await client.get("/dashboard/test/list")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Bulk" not in response.text
    assert "Select all visible items" in response.text
    assert "Keep status" in response.text
    assert "Priority" in response.text
    assert "Leave unchanged" in response.text
    assert "FEAT-0001" in response.text
    assert "bulk.action" not in response.text
    assert "nav.import_history" not in response.text
    assert "nav.import_files" not in response.text


async def test_dashboard_bulk_update_preserves_current_list_url(dashboard_client):
    client, Session = dashboard_client

    response = await client.post(
        "/dashboard/test/items/bulk",
        data={
            "next": "/dashboard/test/list?view=active&kind=feature&kind=bug",
            "local_ids": ["FEAT-0001", "FEAT-0002"],
            "bulk_action": "update",
            "bulk_kind": "bug",
            "bulk_status": "in_progress",
            "bulk_tag_mode": "add",
            "bulk_tags": "triaged",
            "bulk_branch_mode": "replace",
            "bulk_applies_to": "next",
            "custom_field__priority": "high",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/dashboard/test/list?view=active&kind=feature&kind=bug"
    )
    assert "bulk_count=2" in response.headers["location"]

    async with Session() as session:
        svc = ItemService(ItemRepo(session), _registry(), session)
        one = await svc.get("test", "FEAT-0001")
        two = await svc.get("test", "FEAT-0002")

    assert [
        (item.kind, item.status, item.tags, item.applies_to, item.custom_fields)
        for item in [one, two]
    ] == [
        ("bug", "in_progress", ["triaged"], ["next"], {"priority": "high"}),
        ("bug", "in_progress", ["triaged"], ["next"], {"priority": "high"}),
    ]


async def test_dashboard_bulk_update_requires_selection(dashboard_client):
    client, _Session = dashboard_client

    response = await client.post(
        "/dashboard/test/items/bulk",
        data={"next": "/dashboard/test/list", "bulk_action": "update"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "bulk_error=" in response.headers["location"]
