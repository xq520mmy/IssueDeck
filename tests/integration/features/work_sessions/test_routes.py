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
from issuedeck.features.work_sessions.routes import router as work_sessions_router


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"test": ProjectConfig(
            key="test",
            name="Test",
            kinds={"feature": KindConfig(label="Feature", prefix="FEAT")},
            statuses={
                "proposed": StatusConfig(label="P"),
                "in_progress": StatusConfig(label="I"),
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
    app.include_router(work_sessions_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    await engine.dispose()


async def test_work_session_routes_roundtrip(client):
    r = await client.post(
        "/api/v1/projects/test/items",
        json={"kind": "feature", "title": "Track agent session"},
    )
    assert r.status_code == 201, r.text

    r = await client.post(
        "/api/v1/projects/test/work-sessions",
        json={
            "local_id": "FEAT-0001",
            "agent_name": "codex",
            "goal": "Implement a useful feature.",
            "branch": "main",
        },
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]
    assert r.json()["status"] == "active"

    r = await client.post(
        f"/api/v1/projects/test/work-sessions/{session_id}/updates",
        json={"message": "API route works.", "update_type": "progress"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["update_count"] == 2

    r = await client.get("/api/v1/projects/test/work-sessions?status=active")
    assert r.status_code == 200, r.text
    assert [session["id"] for session in r.json()["sessions"]] == [session_id]

    r = await client.post(
        f"/api/v1/projects/test/work-sessions/{session_id}/finish",
        json={"summary": "Finished.", "status": "completed"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"

    r = await client.get(f"/api/v1/projects/test/work-sessions/{session_id}")
    assert r.status_code == 200, r.text
    assert r.json()["updates"][-1]["update_type"] == "completed"


async def test_work_session_update_finished_session_rejected(client):
    await client.post(
        "/api/v1/projects/test/items",
        json={"kind": "feature", "title": "Track agent session"},
    )
    r = await client.post(
        "/api/v1/projects/test/work-sessions",
        json={
            "local_id": "FEAT-0001",
            "agent_name": "codex",
            "goal": "Implement a useful feature.",
        },
    )
    session_id = r.json()["id"]
    await client.post(f"/api/v1/projects/test/work-sessions/{session_id}/finish", json={})

    r = await client.post(
        f"/api/v1/projects/test/work-sessions/{session_id}/updates",
        json={"message": "Too late."},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_transition"
