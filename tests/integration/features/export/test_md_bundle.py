
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from issuedeck.core.config import (
    BranchConfig,
    ConfigRegistry,
    KindConfig,
    ProjectConfig,
    ServerConfig,
    StatusConfig,
)
from issuedeck.features.export.md_bundle import export_md_bundle
from issuedeck.features.items.models import Base
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import CreateItemRequest, ShipItemRequest
from issuedeck.features.items.service import ItemService


def _registry():
    return ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"p": ProjectConfig(
            key="p", name="P",
            kinds={"feature": KindConfig(label="Feature", prefix="FEAT")},
            statuses={
                "proposed": StatusConfig(label="P"),
                "done": StatusConfig(label="D", terminal=True, requires_ship=True),
            },
            branches=[BranchConfig(key="main", label="Main")],
        )},
    )


@pytest.fixture
async def session_and_registry():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        reg = _registry()
        svc = ItemService(ItemRepo(s), reg, s)
        await svc.create("p", CreateItemRequest(
            kind="feature", title="First", body="Body one", tags=["hot"],
        ))
        await svc.create("p", CreateItemRequest(
            kind="feature", title="Second", body="Body two",
        ))
        await svc.ship("p", "FEAT-0002", ShipItemRequest(
            branch="main", version="0.1.0", commits=["abc"],
        ))
        yield s, reg
    await engine.dispose()


async def test_md_bundle_writes_one_file_per_item(tmp_path, session_and_registry):
    session, reg = session_and_registry
    report = await export_md_bundle(
        session=session, registry=reg, project_key="p", out_dir=tmp_path / "out",
    )
    assert report.items_written == 2
    items_dir = tmp_path / "out" / "items"
    files = sorted(items_dir.glob("*.md"))
    assert [f.name for f in files] == ["FEAT-0001.md", "FEAT-0002.md"]

    content1 = files[0].read_text(encoding="utf-8")
    assert content1.startswith("---")
    assert "id: FEAT-0001" in content1
    assert "title: First" in content1
    assert "Body one" in content1

    content2 = files[1].read_text(encoding="utf-8")
    assert "shipped_in_main: 0.1.0" in content2
    assert "- abc" in content2
