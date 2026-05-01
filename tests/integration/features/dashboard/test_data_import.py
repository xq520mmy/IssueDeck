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
from issuedeck.features.dashboard.routes import router as dashboard_router
from issuedeck.features.items.models import Base, ImportBatch, Item, ItemTag


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


async def test_data_import_form_renders(dashboard_client):
    client, _Session = dashboard_client

    response = await client.get("/dashboard/test/imports/files")

    assert response.status_code == 200
    assert "Import Files" in response.text
    assert "CSV" in response.text
    assert "JSON" in response.text
    assert "Markdown" in response.text


async def test_import_pages_do_not_render_raw_i18n_keys(dashboard_client):
    client, _Session = dashboard_client
    raw_keys = ("nav.import_history", "nav.import_files", "bulk.action")

    for lang in ("en", "zh-CN"):
        client.cookies.set("issuedeck_lang", lang)
        for path in (
            "/dashboard/test/list",
            "/dashboard/test/imports/github",
            "/dashboard/test/imports/files",
            "/dashboard/test/imports",
        ):
            response = await client.get(path)

            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            for key in raw_keys:
                assert key not in response.text


async def test_data_import_csv_preview_does_not_write_items(dashboard_client):
    client, Session = dashboard_client

    response = await client.post(
        "/dashboard/test/imports/files",
        data={
            "source_type": "csv",
            "kind": "feature",
            "default_status": "proposed",
            "status_maps": "closed=done",
            "mode": "dry_run",
            "applies_to": "main",
        },
        files={"source_file": ("items.csv", "title,status\nCSV task,closed\n", "text/csv")},
    )

    assert response.status_code == 200, response.text
    assert "Rows" in response.text
    assert "Triage this import" not in response.text
    assert "/dashboard/test/list?tag=csv-import-" not in response.text
    async with Session() as session:
        item_count = await session.scalar(select(func.count()).select_from(Item))
    assert item_count == 0


@pytest.mark.parametrize(
    ("source_type", "filename", "content", "expected_title", "expected_status", "tag_prefix"),
    [
        (
            "csv",
            "items.csv",
            "title,status,tags\nCSV task,closed,alpha\n",
            "CSV task",
            "done",
            "csv-import-",
        ),
        (
            "json",
            "items.json",
            '{"items":[{"title":"JSON task","state":"closed","labels":["beta"]}]}',
            "JSON task",
            "done",
            "json-import-",
        ),
        (
            "markdown",
            "items.md",
            "- [ ] Markdown task https://github.com/acme/repo/issues/1\n",
            "Markdown task https://github.com/acme/repo/issues/1",
            "proposed",
            "markdown-import-",
        ),
    ],
)
async def test_data_import_submit_writes_items(
    dashboard_client,
    source_type,
    filename,
    content,
    expected_title,
    expected_status,
    tag_prefix,
):
    client, Session = dashboard_client

    response = await client.post(
        "/dashboard/test/imports/files",
        data={
            "source_type": source_type,
            "kind": "feature",
            "default_status": "proposed",
            "tags": "uploaded",
            "status_maps": "closed=done",
            "mode": "import",
            "applies_to": "main",
        },
        files={"source_file": (filename, content, "text/plain")},
    )

    assert response.status_code == 200, response.text
    assert "Written" in response.text
    assert "Triage this import" in response.text
    assert f"/dashboard/test/list?tag={tag_prefix}" in response.text
    async with Session() as session:
        items = (await session.execute(select(Item))).scalars().all()
        tags = (await session.execute(select(ItemTag.tag))).scalars().all()
        batches = (await session.execute(select(ImportBatch))).scalars().all()

    assert [(item.local_id, item.title, item.status) for item in items] == [
        ("FEAT-0001", expected_title, expected_status)
    ]
    assert "uploaded" in tags
    assert any(tag.startswith(tag_prefix) for tag in tags)
    assert [(batch.source_type, batch.source_name, batch.items_written) for batch in batches] == [
        (source_type, filename, 1)
    ]
    assert batches[0].batch_tag.startswith(tag_prefix)

    history_response = await client.get("/dashboard/test/imports")

    assert history_response.status_code == 200
    assert "Import History" in history_response.text
    assert filename in history_response.text
    assert f"/dashboard/test/list?tag={tag_prefix}" in history_response.text


async def test_import_history_can_soft_delete_batch(dashboard_client):
    client, Session = dashboard_client

    import_response = await client.post(
        "/dashboard/test/imports/files",
        data={
            "source_type": "csv",
            "kind": "feature",
            "default_status": "proposed",
            "tags": "uploaded",
            "mode": "import",
            "applies_to": "main",
        },
        files={"source_file": ("items.csv", "title\nUndo me\n", "text/csv")},
    )

    assert import_response.status_code == 200, import_response.text
    async with Session() as session:
        batch_tag = await session.scalar(select(ImportBatch.batch_tag))

    assert batch_tag is not None
    delete_response = await client.post(
        f"/dashboard/test/imports/{batch_tag}/delete",
        follow_redirects=False,
    )

    assert delete_response.status_code == 303
    assert "deleted_count=1" in delete_response.headers["location"]
    async with Session() as session:
        item = await session.scalar(select(Item).where(Item.local_id == "FEAT-0001"))

    assert item is not None
    assert item.deleted_at is not None

    history_response = await client.get(delete_response.headers["location"])

    assert history_response.status_code == 200
    assert "Soft-deleted 1 item(s)" in history_response.text
