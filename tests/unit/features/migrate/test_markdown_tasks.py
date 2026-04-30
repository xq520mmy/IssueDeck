import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from issuedeck.core.config import (
    BranchConfig,
    ConfigRegistry,
    KindConfig,
    ProjectConfig,
    ServerConfig,
    StatusConfig,
)
from issuedeck.features.items.models import Base, Item, ItemExternalLink, ItemTag
from issuedeck.features.migrate.markdown_tasks import (
    import_markdown_task_list,
    parse_markdown_task_list,
)


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"sample": ProjectConfig(
            key="sample",
            name="Sample",
            kinds={"feature": KindConfig(label="Feature", prefix="FEAT")},
            statuses={
                "proposed": StatusConfig(label="Proposed"),
                "done": StatusConfig(label="Done", terminal=True),
            },
            branches=[BranchConfig(key="main", label="Main")],
        )},
    )


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


def test_parse_markdown_task_list_skips_checked_by_default(tmp_path):
    source = tmp_path / "TODO.md"
    source.write_text(
        "\n".join([
            "# Tasks",
            "- [ ] Import open task https://github.com/example/repo/issues/42",
            "  Keep the source line in the body.",
            "- [x] Already handled",
        ]),
        encoding="utf-8",
    )

    tasks, report = parse_markdown_task_list(source)

    assert report.tasks_found == 2
    assert report.skipped_checked == 1
    assert report.items_planned == 1
    assert tasks[0].title == "Import open task https://github.com/example/repo/issues/42"
    assert tasks[0].notes == ["Keep the source line in the body."]
    assert tasks[0].external_links == [{
        "link_type": "github_issue",
        "label": "Issue #42",
        "url": "https://github.com/example/repo/issues/42",
    }]


def test_parse_markdown_task_list_can_include_checked(tmp_path):
    source = tmp_path / "TODO.md"
    source.write_text("- [x] Already handled\n", encoding="utf-8")

    tasks, report = parse_markdown_task_list(source, include_checked=True)

    assert report.tasks_found == 1
    assert report.checked_tasks == 1
    assert report.skipped_checked == 0
    assert tasks[0].checked is True


async def test_import_markdown_task_list_writes_items(session, tmp_path):
    source = tmp_path / "TODO.md"
    source.write_text(
        "\n".join([
            "- [ ] Open task",
            "- [x] Closed task https://github.com/example/repo/pull/7",
        ]),
        encoding="utf-8",
    )

    report = await import_markdown_task_list(
        source,
        "sample",
        _registry(),
        session,
        kind="feature",
        tags=["imported"],
        applies_to=None,
        include_checked=True,
        dry_run=False,
    )

    assert report.items_written == 2
    items = (await session.execute(select(Item).order_by(Item.local_id))).scalars().all()
    assert [(item.local_id, item.title, item.status) for item in items] == [
        ("FEAT-0001", "Open task", "proposed"),
        ("FEAT-0002", "Closed task https://github.com/example/repo/pull/7", "done"),
    ]
    tags = (await session.execute(select(ItemTag.tag).order_by(ItemTag.tag))).scalars().all()
    assert tags == ["imported", "imported", "markdown", "markdown"]
    link = (await session.execute(select(ItemExternalLink))).scalar_one()
    assert link.link_type == "github_pr"
    assert link.url == "https://github.com/example/repo/pull/7"
