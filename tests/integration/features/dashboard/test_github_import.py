import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
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
from issuedeck.features.dashboard import routes as dashboard_routes
from issuedeck.features.dashboard.routes import router as dashboard_router
from issuedeck.features.items.models import Base, Item, ItemTag
from issuedeck.features.migrate.github_issues import (
    GitHubIssueImportReport,
    GitHubIssueRow,
)


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
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


@pytest.fixture
async def dashboard_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    app.state.registry = _registry()
    app.state.session_factory = Session
    install_error_handlers(app)
    app.include_router(dashboard_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, Session
    await engine.dispose()


def _github_rows() -> list[GitHubIssueRow]:
    return [
        GitHubIssueRow(
            number=42,
            title="Import me",
            body="Imported body",
            state="closed",
            labels=["bug"],
            html_url="https://github.com/example/repo/issues/42",
            api_url="https://api.github.com/repos/example/repo/issues/42",
            author="octo",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-02T00:00:00Z",
            comments=3,
            is_pull_request=False,
        )
    ]


async def test_github_import_form_renders(dashboard_client):
    client, _Session = dashboard_client

    response = await client.get("/dashboard/test/imports/github")

    assert response.status_code == 200
    assert "Import GitHub Issues" in response.text
    assert "owner/repo" in response.text


async def test_github_import_form_uses_chinese_locale(dashboard_client):
    client, _Session = dashboard_client

    response = await client.get(
        "/dashboard/test/imports/github",
        headers={"Cookie": "issuedeck_lang=zh-CN"},
    )

    assert response.status_code == 200
    assert "导入 GitHub Issues" in response.text
    assert "预览导入" in response.text


async def test_github_import_preview_does_not_write_items(dashboard_client, monkeypatch):
    client, Session = dashboard_client

    async def fake_fetch(repo_ref, **kwargs):
        assert repo_ref.owner == "example"
        assert repo_ref.repo == "repo"
        assert kwargs["state"] == "all"
        assert kwargs["labels"] == ["bug", "help wanted"]
        assert kwargs["include_pulls"] is True
        return _github_rows(), GitHubIssueImportReport(issues_fetched=2, pulls_skipped=1)

    monkeypatch.setattr(dashboard_routes, "fetch_github_issue_rows", fake_fetch)

    response = await client.post(
        "/dashboard/test/imports/github",
        data={
            "repo": "example/repo",
            "kind": "feature",
            "default_status": "proposed",
            "state": "all",
            "limit": "10",
            "labels": "bug, help wanted",
            "tags": "imported",
            "status_maps": "closed=done",
            "include_pulls": "true",
            "mode": "dry_run",
            "applies_to": "main",
        },
    )

    assert response.status_code == 200, response.text
    assert "example/repo" in response.text
    assert "Planned" in response.text
    assert "Triage this import" not in response.text
    assert "/dashboard/test/list?tag=github-import-" not in response.text
    async with Session() as session:
        item_count = await session.scalar(select(func.count()).select_from(Item))
    assert item_count == 0


async def test_github_import_submit_writes_items(dashboard_client, monkeypatch):
    client, Session = dashboard_client

    async def fake_fetch(_repo_ref, **_kwargs):
        return _github_rows(), GitHubIssueImportReport(issues_fetched=1, pulls_skipped=0)

    monkeypatch.setattr(dashboard_routes, "fetch_github_issue_rows", fake_fetch)

    response = await client.post(
        "/dashboard/test/imports/github",
        data={
            "repo": "example/repo",
            "kind": "feature",
            "state": "all",
            "limit": "10",
            "status_maps": "closed=done",
            "mode": "import",
            "applies_to": "main",
        },
    )

    assert response.status_code == 200, response.text
    assert "Written" in response.text
    assert "Triage this import" in response.text
    assert "/dashboard/test/list?tag=github-import-" in response.text
    async with Session() as session:
        items = (await session.execute(select(Item))).scalars().all()
        tags = (await session.execute(select(ItemTag.tag))).scalars().all()
    assert [(item.local_id, item.title, item.status) for item in items] == [
        ("FEAT-0001", "Import me", "done")
    ]
    assert any(tag.startswith("github-import-") for tag in tags)
