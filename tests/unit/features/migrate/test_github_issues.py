import httpx
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
from issuedeck.features.migrate.csv_items import parse_status_map_options
from issuedeck.features.migrate.github_issues import (
    GitHubIssueRow,
    fetch_github_issue_rows,
    import_github_issue_rows,
    parse_github_repo,
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
                "in_progress": StatusConfig(label="In Progress"),
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


def test_parse_github_repo_accepts_owner_repo_and_url():
    assert parse_github_repo("example/repo").owner == "example"
    assert parse_github_repo("https://github.com/example/repo.git").repo == "repo"

    with pytest.raises(ValueError, match="owner/repo"):
        parse_github_repo("example")


async def test_fetch_github_issue_rows_filters_pull_requests():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params.multi_items())
        captured["version"] = request.headers.get("x-github-api-version")
        captured["auth"] = request.headers.get("authorization")
        if request.url.params.get("page") != "1":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json=[
                {
                    "number": 42,
                    "title": "Fix auth",
                    "body": "Body",
                    "state": "open",
                    "labels": [{"name": "bug"}],
                    "html_url": "https://github.com/example/repo/issues/42",
                    "url": "https://api.github.com/repos/example/repo/issues/42",
                    "user": {"login": "octo"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-02T00:00:00Z",
                    "comments": 3,
                },
                {
                    "number": 7,
                    "title": "Open PR",
                    "state": "open",
                    "html_url": "https://github.com/example/repo/pull/7",
                    "pull_request": {},
                },
            ],
        )

    rows, report = await fetch_github_issue_rows(
        parse_github_repo("example/repo"),
        token="ghp_test",
        labels=["bug", "p1"],
        since="2026-01-01T00:00:00Z",
        limit=10,
        transport=httpx.MockTransport(handler),
    )

    assert captured["path"] == "/repos/example/repo/issues"
    assert captured["params"]["labels"] == "bug,p1"
    assert captured["params"]["since"] == "2026-01-01T00:00:00Z"
    assert captured["version"] == "2022-11-28"
    assert captured["auth"] == "Bearer ghp_test"
    assert report.issues_fetched == 2
    assert report.pulls_skipped == 1
    assert len(rows) == 1
    assert rows[0].number == 42
    assert rows[0].labels == ["bug"]


async def test_import_github_issue_rows_writes_items_and_skips_existing(session):
    rows = [
        GitHubIssueRow(
            number=42,
            title="Fix auth",
            body="Imported body",
            state="open",
            labels=["bug", "p1"],
            html_url="https://github.com/example/repo/issues/42",
            api_url="https://api.github.com/repos/example/repo/issues/42",
            author="octo",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-02T00:00:00Z",
            comments=3,
            is_pull_request=False,
        ),
        GitHubIssueRow(
            number=43,
            title="Closed issue",
            body="",
            state="closed",
            labels=["docs"],
            html_url="https://github.com/example/repo/issues/43",
            api_url="https://api.github.com/repos/example/repo/issues/43",
            author="octo",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-02T00:00:00Z",
            comments=0,
            is_pull_request=False,
        ),
    ]

    report = await import_github_issue_rows(
        rows,
        "sample",
        _registry(),
        session,
        kind="feature",
        tags=["imported"],
        applies_to=None,
        status_map=parse_status_map_options(["closed=done"]),
        dry_run=False,
    )

    assert report.items_written == 2
    assert report.status_mapped == 2
    items = (await session.execute(select(Item).order_by(Item.local_id))).scalars().all()
    assert [(item.local_id, item.status, item.title) for item in items] == [
        ("FEAT-0001", "proposed", "Fix auth"),
        ("FEAT-0002", "done", "Closed issue"),
    ]
    tags = (await session.execute(select(ItemTag.tag).order_by(ItemTag.tag))).scalars().all()
    assert tags == ["bug", "docs", "github", "github", "imported", "imported", "p1"]
    links = (await session.execute(
        select(ItemExternalLink.link_type, ItemExternalLink.url).order_by(ItemExternalLink.url)
    )).all()
    assert links == [
        ("github_issue", "https://github.com/example/repo/issues/42"),
        ("github_issue", "https://github.com/example/repo/issues/43"),
    ]

    second = await import_github_issue_rows(
        rows,
        "sample",
        _registry(),
        session,
        kind="feature",
        tags=[],
        applies_to=None,
        dry_run=True,
    )
    assert second.existing_skipped == 2
    assert second.items_planned == 0
