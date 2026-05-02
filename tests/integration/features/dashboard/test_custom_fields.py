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
from issuedeck.features.items.service import ItemService


@pytest.fixture
async def dashboard_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    registry = ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"test": ProjectConfig(
            key="test",
            name="Test",
            kinds={"feature": KindConfig(label="Feature", prefix="FEAT")},
            statuses={"proposed": StatusConfig(label="Proposed")},
            branches=[BranchConfig(key="main", label="Main")],
            custom_fields={
                "priority": CustomFieldConfig(
                    label="Priority",
                    type="select",
                    required=True,
                    options=["low", "high"],
                ),
                "estimate": CustomFieldConfig(label="Estimate", type="number"),
                "customer_impact": CustomFieldConfig(
                    label="Customer impact",
                    type="checkbox",
                ),
            },
        )},
    )

    app = FastAPI()
    app.state.registry = registry
    app.state.session_factory = Session
    install_error_handlers(app)
    app.include_router(dashboard_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, Session, registry
    await engine.dispose()


async def test_dashboard_item_form_renders_and_saves_custom_fields(dashboard_client):
    client, Session, registry = dashboard_client

    form = await client.get("/dashboard/test/items-new")

    assert form.status_code == 200
    assert "Custom fields" in form.text
    assert "Priority" in form.text
    assert 'name="custom_field__estimate"' in form.text

    response = await client.post(
        "/dashboard/test/items-new",
        data={
            "kind": "feature",
            "title": "Dashboard custom fields",
            "custom_field__priority": "high",
            "custom_field__estimate": "8",
            "custom_field__customer_impact": "true",
            "applies_to": "main",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard/test/items/FEAT-0001"

    async with Session() as session:
        svc = ItemService(ItemRepo(session), registry, session)
        item = await svc.get("test", "FEAT-0001")

    assert item.custom_fields == {
        "priority": "high",
        "estimate": 8,
        "customer_impact": True,
    }


async def test_dashboard_item_detail_shows_custom_fields(dashboard_client):
    client, _Session, _registry = dashboard_client
    await client.post(
        "/dashboard/test/items-new",
        data={
            "kind": "feature",
            "title": "Dashboard custom fields",
            "custom_field__priority": "low",
            "custom_field__estimate": "3",
            "applies_to": "main",
        },
    )

    response = await client.get("/dashboard/test/items/FEAT-0001")

    assert response.status_code == 200
    assert "Priority" in response.text
    assert "low" in response.text
    assert "Estimate" in response.text
    assert "3" in response.text
