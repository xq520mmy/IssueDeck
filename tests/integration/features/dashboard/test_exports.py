import json
import zipfile
from io import BytesIO

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
from issuedeck.features.dashboard.routes import router as dashboard_router
from issuedeck.features.items.models import Base
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import CreateItemRequest
from issuedeck.features.items.service import ItemService


@pytest.fixture
async def dashboard_client(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    registry = ConfigRegistry(
        server=ServerConfig(api_token="t", projects_dir=tmp_path),
        projects={"test": ProjectConfig(
            key="test",
            name="Test",
            kinds={"feature": KindConfig(label="Feature", prefix="FEAT")},
            statuses={
                "proposed": StatusConfig(label="Proposed"),
                "done": StatusConfig(label="Done", terminal=True),
            },
            branches=[BranchConfig(key="main", label="Main")],
        )},
    )
    async with Session() as session:
        svc = ItemService(ItemRepo(session), registry, session)
        await svc.create(
            "test",
            CreateItemRequest(kind="feature", title="Snapshot me", body="Body"),
        )

    app = FastAPI()
    app.state.registry = registry
    app.state.session_factory = Session
    install_error_handlers(app)
    app.include_router(dashboard_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        yield client
    await engine.dispose()


async def test_dashboard_overview_links_audit_bundle(dashboard_client):
    response = await dashboard_client.get("/dashboard/test")

    assert response.status_code == 200
    assert "/dashboard/test/exports/audit-bundle" in response.text
    assert "Export snapshot" in response.text


async def test_dashboard_downloads_audit_bundle_zip(dashboard_client):
    response = await dashboard_client.get("/dashboard/test/exports/audit-bundle")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == (
        'attachment; filename="test-audit-bundle.zip"'
    )
    with zipfile.ZipFile(BytesIO(response.content)) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["project_key"] == "test"
        assert manifest["counts"]["items"] == 1
        items = json.loads(bundle.read("items.json"))
        assert items[0]["title"] == "Snapshot me"
