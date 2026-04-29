import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from issuedeck.core.config import (
    BranchConfig,
    ConfigRegistry,
    KindConfig,
    ProjectConfig,
    ServerConfig,
    StatusConfig,
)
from issuedeck.core.errors import install_error_handlers
from issuedeck.features.items.models import Base
from issuedeck.features.items.routes import router as items_router
from issuedeck.features.projects.routes import router as projects_router


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    app.state.registry = ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={
            "a": ProjectConfig(
                key="a", name="A",
                kinds={"feature": KindConfig(label="Feature", prefix="FEAT")},
                statuses={"proposed": StatusConfig(label="P")},
                branches=[BranchConfig(key="main", label="Main")],
            ),
            "b": ProjectConfig(
                key="b", name="B", description="second",
                kinds={"bug": KindConfig(label="Bug", prefix="BUG")},
                statuses={"open": StatusConfig(label="Open")},
            ),
        },
    )
    app.state.session_factory = Session
    install_error_handlers(app)
    app.include_router(projects_router)
    app.include_router(items_router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c
    await engine.dispose()


async def test_list_projects(client):
    r = await client.get("/api/v1/projects")
    assert r.status_code == 200
    body = r.json()
    keys = {p["key"] for p in body["projects"]}
    assert keys == {"a", "b"}


async def test_get_project_config(client):
    r = await client.get("/api/v1/projects/a")
    assert r.status_code == 200
    assert r.json()["key"] == "a"
    assert "feature" in r.json()["kinds"]


async def test_get_unknown_project(client):
    r = await client.get("/api/v1/projects/unknown")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"


async def test_list_projects_includes_item_count(client):
    r = await client.post("/api/v1/projects/a/items",
                          json={"kind": "feature", "title": "x"})
    assert r.status_code == 201

    r = await client.get("/api/v1/projects")
    counts = {p["key"]: p["item_count"] for p in r.json()["projects"]}
    assert counts["a"] == 1
    assert counts["b"] == 0
