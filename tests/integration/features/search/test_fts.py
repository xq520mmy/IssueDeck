import pytest

from issuedeck.core.config import (
    ConfigRegistry,
    KindConfig,
    ProjectConfig,
    ServerConfig,
    StatusConfig,
)
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import CreateItemRequest, UpdateItemRequest
from issuedeck.features.items.service import ItemService
from issuedeck.features.search.repo import SearchRepo
from issuedeck.features.search.service import SearchService


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"p": ProjectConfig(
            key="p", name="P",
            kinds={"feature": KindConfig(label="Feature", prefix="FEAT")},
            statuses={"proposed": StatusConfig(label="P")},
        )},
    )


@pytest.fixture
async def ctx(migrated_session):
    reg = _registry()
    items = ItemService(ItemRepo(migrated_session), reg, migrated_session)
    await items.create("p", CreateItemRequest(
        kind="feature", title="Add caching layer", body="Redis-based cache",
    ))
    await items.create("p", CreateItemRequest(
        kind="feature", title="Refactor database code", body="SQLAlchemy 2.0",
    ))
    await items.create("p", CreateItemRequest(
        kind="feature", title="Documentation updates", body="README polish",
    ))
    search = SearchService(SearchRepo(migrated_session), reg, migrated_session)
    return items, search


async def test_search_returns_title_match(ctx):
    _, search = ctx
    res = await search.search("p", "cache")
    assert len(res.items) == 1
    assert res.items[0].local_id == "FEAT-0001"


async def test_search_body_match(ctx):
    _, search = ctx
    res = await search.search("p", "redis")
    assert len(res.items) == 1


async def test_search_reflects_update(ctx):
    items, search = ctx
    await items.update("p", "FEAT-0003", UpdateItemRequest(
        body="Elasticsearch integration",
    ))
    res = await search.search("p", "elasticsearch")
    assert len(res.items) == 1
    assert res.items[0].local_id == "FEAT-0003"


async def test_search_no_match(ctx):
    _, search = ctx
    res = await search.search("p", "nonexistent")
    assert len(res.items) == 0


async def test_search_excludes_deleted(ctx):
    items, search = ctx
    await items.soft_delete("p", "FEAT-0001")
    res = await search.search("p", "cache")
    assert len(res.items) == 0
