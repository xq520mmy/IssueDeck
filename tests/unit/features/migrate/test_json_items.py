import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from issuedeck.core.config import (
    BranchConfig,
    ConfigRegistry,
    CustomFieldConfig,
    KindConfig,
    ProjectConfig,
    ServerConfig,
    StatusConfig,
)
from issuedeck.features.items.models import Base, Item, ItemExternalLink, ItemTag
from issuedeck.features.migrate.csv_items import parse_status_map_options
from issuedeck.features.migrate.json_items import (
    JsonItemMapping,
    import_json_items,
    parse_json_items,
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


def _registry_with_custom_fields():
    registry = _registry()
    project = registry.project("sample")
    project.custom_fields = {
        "priority": CustomFieldConfig(
            label="Priority",
            type="select",
            required=True,
            options=["low", "high"],
        ),
        "customer_impact": CustomFieldConfig(
            label="Customer impact",
            type="checkbox",
        ),
    }
    return registry


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


def test_parse_json_items_accepts_wrapped_exports_and_label_objects(tmp_path):
    source = tmp_path / "issues.json"
    source.write_text(
        json.dumps({
            "issues": [
                {
                    "title": "Import JSON export",
                    "state": "open",
                    "labels": [{"name": "migration"}, {"name": "json"}],
                    "html_url": "https://github.com/example/repo/issues/42",
                    "number": 42,
                },
                {},
            ],
        }),
        encoding="utf-8",
    )
    mapping = JsonItemMapping.from_alias_options([], presets=["github"])

    rows, report = parse_json_items(source, mapping=mapping)

    assert report.objects_found == 1
    assert report.objects_skipped == 1
    assert report.items_planned == 1
    assert rows[0].title == "Import JSON export"
    assert rows[0].tags == ["migration", "json"]
    assert rows[0].source_id == "42"
    assert rows[0].external_links == [{
        "link_type": "github_issue",
        "label": "Issue #42",
        "url": "https://github.com/example/repo/issues/42",
    }]


async def test_import_json_items_writes_items(session, tmp_path):
    source = tmp_path / "issues.json"
    source.write_text(
        json.dumps([
            {
                "title": "Fix login",
                "type": "Bug",
                "state": "Verified",
                "labels": ["auth", {"name": "urgent"}],
                "branches": ["Main"],
                "html_url": "https://github.com/example/repo/issues/42",
                "body": "Imported body",
                "number": 42,
            },
            {
                "title": "Ship keyboard flow",
                "type": "Feature",
                "state": "In Progress",
                "labels": ["ux"],
                "branches": ["release"],
                "html_url": "https://github.com/example/repo/pull/7",
                "number": 7,
            },
        ]),
        encoding="utf-8",
    )

    report = await import_json_items(
        source,
        "sample",
        _registry(),
        session,
        kind="feature",
        tags=["imported"],
        applies_to=None,
        status_map=parse_status_map_options(["Verified=done"]),
        mapping=JsonItemMapping.from_alias_options([], presets=["github"]),
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
    assert tags == ["auth", "imported", "imported", "json", "json", "urgent", "ux"]
    links = (
        (await session.execute(select(ItemExternalLink.link_type).order_by(ItemExternalLink.url)))
        .scalars()
        .all()
    )
    assert links == ["github_issue", "github_pr"]


async def test_import_json_items_maps_custom_fields(session, tmp_path):
    source = tmp_path / "issues.json"
    source.write_text(
        json.dumps([{
            "title": "Custom JSON import",
            "priority": "high",
            "impact": True,
        }]),
        encoding="utf-8",
    )
    mapping = JsonItemMapping.from_alias_options([
        "custom.priority=priority",
        "custom.customer_impact=impact",
    ])

    report = await import_json_items(
        source,
        "sample",
        _registry_with_custom_fields(),
        session,
        kind="feature",
        mapping=mapping,
        dry_run=False,
    )

    assert report.items_written == 1
    assert report.custom_fields == 2
    item = await session.scalar(select(Item).where(Item.local_id == "FEAT-0001"))
    assert item is not None
    assert json.loads(item.custom_fields_json) == {
        "customer_impact": True,
        "priority": "high",
    }
