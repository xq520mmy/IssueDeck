import re

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


def _assert_stat(html: str, label: str, value: int) -> None:
    pattern = rf"<dt[^>]*>{re.escape(label)}</dt>\s*<dd[^>]*>{value}</dd>"
    assert re.search(pattern, html), f"missing stat {label}={value}"


def _assert_action_disabled(
    html: str,
    batch_tag: str,
    action: str,
    *,
    disabled: bool,
) -> None:
    pattern = (
        rf'action="/dashboard/test/imports/{re.escape(batch_tag)}/{action}"'
        r"[\s\S]*?<button[^>]*>"
    )
    match = re.search(pattern, html)
    assert match, f"missing {action} button for {batch_tag}"
    assert bool(re.search(r"\sdisabled(?:\s|=|>)", match.group(0))) is disabled


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


async def test_import_history_can_restore_soft_deleted_batch(dashboard_client):
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
        files={"source_file": ("items.csv", "title\nRestore me\n", "text/csv")},
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
    restore_response = await client.post(
        f"/dashboard/test/imports/{batch_tag}/restore",
        follow_redirects=False,
    )

    assert restore_response.status_code == 303
    assert "restored_count=1" in restore_response.headers["location"]
    async with Session() as session:
        item = await session.scalar(select(Item).where(Item.local_id == "FEAT-0001"))

    assert item is not None
    assert item.deleted_at is None

    history_response = await client.get(restore_response.headers["location"])

    assert history_response.status_code == 200
    assert "Restored 1 item(s)" in history_response.text


async def test_import_history_shows_batch_item_state_counts(dashboard_client):
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
        files={"source_file": ("items.csv", "title\nCount me\n", "text/csv")},
    )

    assert import_response.status_code == 200, import_response.text
    async with Session() as session:
        batch_tag = await session.scalar(select(ImportBatch.batch_tag))

    assert batch_tag is not None
    history_response = await client.get("/dashboard/test/imports")

    assert history_response.status_code == 200
    _assert_stat(history_response.text, "Active", 1)
    _assert_stat(history_response.text, "Deleted", 0)
    _assert_action_disabled(
        history_response.text, batch_tag, "delete", disabled=False,
    )
    _assert_action_disabled(
        history_response.text, batch_tag, "restore", disabled=True,
    )

    await client.post(
        f"/dashboard/test/imports/{batch_tag}/delete",
        follow_redirects=False,
    )
    deleted_history_response = await client.get("/dashboard/test/imports")

    assert deleted_history_response.status_code == 200
    _assert_stat(deleted_history_response.text, "Active", 0)
    _assert_stat(deleted_history_response.text, "Deleted", 1)
    _assert_action_disabled(
        deleted_history_response.text, batch_tag, "delete", disabled=True,
    )
    _assert_action_disabled(
        deleted_history_response.text, batch_tag, "restore", disabled=False,
    )

    await client.post(
        f"/dashboard/test/imports/{batch_tag}/restore",
        follow_redirects=False,
    )
    restored_history_response = await client.get("/dashboard/test/imports")

    assert restored_history_response.status_code == 200
    _assert_stat(restored_history_response.text, "Active", 1)
    _assert_stat(restored_history_response.text, "Deleted", 0)


async def test_import_history_filters_by_source_and_item_state(dashboard_client):
    client, Session = dashboard_client

    csv_response = await client.post(
        "/dashboard/test/imports/files",
        data={
            "source_type": "csv",
            "kind": "feature",
            "default_status": "proposed",
            "mode": "import",
            "applies_to": "main",
        },
        files={"source_file": ("deleted-batch.csv", "title\nDeleted batch\n", "text/csv")},
    )
    json_response = await client.post(
        "/dashboard/test/imports/files",
        data={
            "source_type": "json",
            "kind": "feature",
            "default_status": "proposed",
            "mode": "import",
            "applies_to": "main",
        },
        files={
            "source_file": (
                "active-batch.json",
                '{"items":[{"title":"Active batch"}]}',
                "application/json",
            ),
        },
    )

    assert csv_response.status_code == 200, csv_response.text
    assert json_response.status_code == 200, json_response.text
    async with Session() as session:
        csv_batch = await session.scalar(
            select(ImportBatch.batch_tag)
            .where(ImportBatch.source_type == "csv")
        )

    assert csv_batch is not None
    delete_response = await client.post(
        f"/dashboard/test/imports/{csv_batch}/delete",
        follow_redirects=False,
    )

    assert delete_response.status_code == 303

    json_history = await client.get("/dashboard/test/imports?source=json")

    assert json_history.status_code == 200
    assert "active-batch.json" in json_history.text
    assert "deleted-batch.csv" not in json_history.text

    deleted_history = await client.get("/dashboard/test/imports?batch_state=deleted")

    assert deleted_history.status_code == 200
    assert "deleted-batch.csv" in deleted_history.text
    assert "active-batch.json" not in deleted_history.text

    active_history = await client.get("/dashboard/test/imports?batch_state=active")

    assert active_history.status_code == 200
    assert "active-batch.json" in active_history.text
    assert "deleted-batch.csv" not in active_history.text


async def test_import_history_paginates_recent_batches(dashboard_client):
    client, Session = dashboard_client

    async with Session() as session:
        for idx in range(26):
            session.add(ImportBatch(
                project_key="test",
                batch_tag=f"csv-import-page-{idx:02d}",
                source_type="csv",
                source_name=f"page-{idx:02d}.csv",
                items_planned=1,
                items_written=1,
                skipped_count=0,
                status_mapped=0,
                external_links=0,
                created_at=f"2026-05-01T00:00:{idx:02d}Z",
                metadata_json="{}",
            ))
        await session.commit()

    first_page = await client.get("/dashboard/test/imports?source=csv")

    assert first_page.status_code == 200
    assert "page-25.csv" in first_page.text
    assert "page-00.csv" not in first_page.text
    assert "Showing 1-25 of 26 recent matches." in first_page.text
    assert "/dashboard/test/imports?source=csv&amp;batch_state=all&amp;page=2" in first_page.text

    second_page = await client.get("/dashboard/test/imports?source=csv&page=2")

    assert second_page.status_code == 200
    assert "page-00.csv" in second_page.text
    assert "page-25.csv" not in second_page.text
    assert "Showing 26-26 of 26 recent matches." in second_page.text
    assert "/dashboard/test/imports?source=csv&amp;batch_state=all&amp;page=1" in second_page.text
