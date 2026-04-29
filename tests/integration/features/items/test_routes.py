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


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"test": ProjectConfig(
            key="test", name="Test",
            kinds={"feature": KindConfig(label="Feature", prefix="FEAT")},
            statuses={
                "proposed": StatusConfig(label="P"),
                "done": StatusConfig(label="D", terminal=True, requires_ship=True),
            },
            branches=[BranchConfig(key="main", label="Main")],
        )},
    )


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    app.state.registry = _registry()
    app.state.session_factory = Session
    install_error_handlers(app)
    app.include_router(items_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    await engine.dispose()


async def test_create_get_list_roundtrip(client):
    r = await client.post(
        "/api/v1/projects/test/items",
        json={
            "kind": "feature",
            "title": "Hello",
            "external_links": [
                {
                    "url": "https://github.com/example/repo/issues/42?from=api",
                }
            ],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["local_id"] == "FEAT-0001"
    assert r.json()["external_links"][0]["label"] == "Issue #42"
    assert r.json()["external_links"][0]["url"] == "https://github.com/example/repo/issues/42"

    r = await client.get("/api/v1/projects/test/items/FEAT-0001")
    assert r.status_code == 200
    assert r.json()["title"] == "Hello"
    assert r.json()["external_links"][0]["link_type"] == "github_issue"

    r = await client.get("/api/v1/projects/test/items")
    assert r.status_code == 200
    assert r.json()["limit"] == 50
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["external_links"][0]["url"].endswith("/issues/42")


async def test_ship_item(client):
    await client.post("/api/v1/projects/test/items",
                      json={"kind": "feature", "title": "x"})
    r = await client.post(
        "/api/v1/projects/test/items/FEAT-0001/ship",
        json={"branch": "main", "version": "0.1.0", "commits": ["abc"]},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"


async def test_append_item_event(client):
    await client.post("/api/v1/projects/test/items",
                      json={"kind": "feature", "title": "x"})
    r = await client.post(
        "/api/v1/projects/test/items/FEAT-0001/events",
        json={
            "event_type": "comment",
            "actor_type": "agent",
            "actor_name": "codex",
            "body": "Captured implementation notes.",
            "metadata": {"source": "route-test"},
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["actor_name"] == "codex"

    r = await client.get("/api/v1/projects/test/items/FEAT-0001")
    assert r.status_code == 200
    assert r.json()["events"][0]["body"] == "Captured implementation notes."


async def test_404_unknown_item(client):
    r = await client.get("/api/v1/projects/test/items/FEAT-9999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "item_not_found"


async def test_422_unknown_kind(client):
    r = await client.post("/api/v1/projects/test/items",
                          json={"kind": "spike", "title": "x"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_kind"


async def test_delete_then_restore(client):
    await client.post("/api/v1/projects/test/items",
                      json={"kind": "feature", "title": "x"})
    r = await client.delete("/api/v1/projects/test/items/FEAT-0001")
    assert r.status_code == 204
    r = await client.get("/api/v1/projects/test/items/FEAT-0001")
    assert r.status_code == 404
    r = await client.post("/api/v1/projects/test/items/FEAT-0001/restore")
    assert r.status_code == 200


async def test_list_only_deleted_route(client):
    await client.post("/api/v1/projects/test/items",
                      json={"kind": "feature", "title": "x"})
    await client.delete("/api/v1/projects/test/items/FEAT-0001")

    r = await client.get("/api/v1/projects/test/items?only_deleted=true")
    assert r.status_code == 200
    assert [item["local_id"] for item in r.json()["items"]] == ["FEAT-0001"]
