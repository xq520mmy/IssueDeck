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
from issuedeck.features.migrate.csv_items import (
    CsvItemMapping,
    import_csv_items,
    parse_csv_items,
    parse_status_map_options,
)


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"sample": ProjectConfig(
            key="sample",
            name="Sample",
            kinds={
                "feature": KindConfig(label="Feature", prefix="FEAT"),
                "bug": KindConfig(label="Bug", prefix="BUG"),
            },
            statuses={
                "proposed": StatusConfig(label="Proposed"),
                "in_progress": StatusConfig(label="In Progress"),
                "done": StatusConfig(label="Done", terminal=True),
            },
            branches=[
                BranchConfig(key="main", label="Main"),
                BranchConfig(key="release", label="Release"),
            ],
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


def test_parse_csv_items_uses_aliases_and_extracts_links(tmp_path):
    source = tmp_path / "issues.csv"
    source.write_text(
        "\n".join([
            "Issue,State,Labels,URL,Description,ID",
            (
                "Import CSV export,open,\"migration,csv\","
                "https://github.com/example/repo/issues/42,Keep notes,GH-42"
            ),
            ",,,,,",
        ]),
        encoding="utf-8",
    )
    mapping = CsvItemMapping.from_alias_options(["title=Issue"], presets=["github"])

    rows, report = parse_csv_items(source, mapping=mapping)

    assert report.rows_found == 1
    assert report.rows_skipped == 1
    assert report.items_planned == 1
    assert rows[0].title == "Import CSV export"
    assert rows[0].tags == ["migration", "csv"]
    assert rows[0].source_id == "GH-42"
    assert rows[0].external_links == [{
        "link_type": "github_issue",
        "label": "Issue #42",
        "url": "https://github.com/example/repo/issues/42",
    }]


async def test_import_csv_items_writes_items(session, tmp_path):
    source = tmp_path / "issues.csv"
    source.write_text(
        "\n".join([
            "Title,Type,State,Labels,Branches,URL,Description,ID",
            (
                "Fix login,Bug,Verified,\"auth;urgent\",Main,"
                "https://github.com/example/repo/issues/42,Imported body,GH-42"
            ),
            (
                "Ship keyboard flow,Feature,In Progress,ux,release,"
                "https://github.com/example/repo/pull/7,,LIN-7"
            ),
        ]),
        encoding="utf-8",
    )

    report = await import_csv_items(
        source,
        "sample",
        _registry(),
        session,
        kind="feature",
        tags=["imported"],
        applies_to=None,
        status_map=parse_status_map_options(["Verified=done"]),
        dry_run=False,
    )

    assert report.items_written == 2
    assert report.status_mapped == 1
    items = (await session.execute(select(Item).order_by(Item.title))).scalars().all()
    assert [(item.local_id, item.kind, item.status, item.title) for item in items] == [
        ("BUG-0001", "bug", "done", "Fix login"),
        ("FEAT-0001", "feature", "in_progress", "Ship keyboard flow"),
    ]
    tags = (await session.execute(select(ItemTag.tag).order_by(ItemTag.tag))).scalars().all()
    assert tags == ["auth", "csv", "csv", "imported", "imported", "urgent", "ux"]
    links = (
        (await session.execute(select(ItemExternalLink.link_type).order_by(ItemExternalLink.url)))
        .scalars()
        .all()
    )
    assert links == ["github_issue", "github_pr"]
