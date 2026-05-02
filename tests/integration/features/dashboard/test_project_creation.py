import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from issuedeck.core.config import ConfigRegistry, ServerConfig
from issuedeck.core.errors import install_error_handlers
from issuedeck.features.dashboard.routes import router as dashboard_router
from issuedeck.features.items.models import Base


@pytest.fixture
async def dashboard_client(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    registry = ConfigRegistry(
        server=ServerConfig(api_token="t", projects_dir=tmp_path),
        projects={},
    )

    app = FastAPI()
    app.state.registry = registry
    app.state.session_factory = Session
    install_error_handlers(app)
    app.include_router(dashboard_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, registry, tmp_path
    await engine.dispose()


async def test_project_form_renders_template_options(dashboard_client):
    client, _registry, _projects_dir = dashboard_client

    response = await client.get("/dashboard/projects-new")

    assert response.status_code == 200
    assert "Basic issue deck" in response.text
    assert "Agent workflow" in response.text
    assert "Software team" in response.text


async def test_project_creation_uses_selected_template(dashboard_client):
    client, registry, projects_dir = dashboard_client

    response = await client.post(
        "/dashboard/projects-new",
        data={
            "key": "agent-lab",
            "name": "Agent Lab",
            "description": "Tracks agent work.",
            "template_key": "agent",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard/agent-lab"

    written = (projects_dir / "agent-lab.toml").read_text(encoding="utf-8")
    assert "[kinds.task]" in written
    assert "[statuses.blocked]" in written
    assert "[statuses.ready_to_ship]" in written

    project = registry.project("agent-lab")
    assert "task" in project.kinds
    assert "blocked" in project.statuses
    assert "ready_to_ship" in project.statuses


async def test_project_creation_rejects_unknown_template(dashboard_client):
    client, _registry, projects_dir = dashboard_client

    response = await client.post(
        "/dashboard/projects-new",
        data={
            "key": "bad-template",
            "name": "Bad Template",
            "template_key": "unknown",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "Choose one of the built-in project templates." in response.text
    assert not (projects_dir / "bad-template.toml").exists()
