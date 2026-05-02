import json
import zipfile

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
from issuedeck.features.export.md_bundle import export_audit_bundle
from issuedeck.features.items.models import Base, ImportBatch
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import CreateItemRequest
from issuedeck.features.items.service import ItemService
from issuedeck.features.relationships.repo import RelationshipRepo
from issuedeck.features.relationships.service import RelationshipService
from issuedeck.features.work_sessions.repo import WorkSessionRepo
from issuedeck.features.work_sessions.schemas import CreateWorkSessionRequest
from issuedeck.features.work_sessions.service import WorkSessionService


def _registry(tmp_path):
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    (projects_dir / "p.toml").write_text(
        'key = "p"\nname = "P"\n[kinds.feature]\nlabel = "Feature"\nprefix = "FEAT"\n'
        '[statuses.proposed]\nlabel = "P"\n',
        encoding="utf-8",
    )
    return ConfigRegistry(
        server=ServerConfig(api_token="t", projects_dir=projects_dir),
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
async def session_and_registry(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        registry = _registry(tmp_path)
        item_repo = ItemRepo(session)
        item_svc = ItemService(item_repo, registry, session)
        await item_svc.create(
            "p",
            CreateItemRequest(
                kind="feature",
                title="First",
                body="Body one",
                tags=["hot"],
                external_links=[{
                    "url": "https://github.com/example/repo/issues/1",
                    "label": "Issue 1",
                }],
            ),
        )
        await item_svc.create(
            "p",
            CreateItemRequest(kind="feature", title="Second", body="Body two"),
        )
        rel_svc = RelationshipService(
            RelationshipRepo(session),
            item_repo,
            registry,
            session,
        )
        await rel_svc.add(
            "p",
            "FEAT-0001",
            to_local_id="FEAT-0002",
            relation_type="blocks",
        )
        work_svc = WorkSessionService(
            WorkSessionRepo(session),
            item_repo,
            registry,
            session,
        )
        await work_svc.start(
            "p",
            CreateWorkSessionRequest(
                local_id="FEAT-0001",
                agent_name="codex",
                goal="Implement the first feature",
                branch="main",
                metadata={"ticket": "fixture"},
            ),
        )
        session.add(ImportBatch(
            project_key="p",
            batch_tag="csv-import-20260502",
            source_type="csv",
            source_name="backlog.csv",
            items_planned=2,
            items_written=2,
            skipped_count=0,
            status_mapped=1,
            external_links=1,
            created_at="2026-05-02T00:00:00+00:00",
            metadata_json='{"source":"fixture"}',
        ))
        await session.commit()
        yield session, registry
    await engine.dispose()


async def test_audit_bundle_writes_project_snapshot(tmp_path, session_and_registry):
    session, registry = session_and_registry
    report = await export_audit_bundle(
        session=session,
        registry=registry,
        project_key="p",
        out_path=tmp_path / "snapshots",
    )

    assert report.bundle_path == tmp_path / "snapshots" / "p-audit-bundle.zip"
    assert report.items_written == 2
    assert report.relationships_written == 2
    assert report.work_sessions_written == 1
    assert report.import_batches_written == 1

    with zipfile.ZipFile(report.bundle_path) as bundle:
        names = set(bundle.namelist())
        assert {
            "manifest.json",
            "project.json",
            "project.toml",
            "items.json",
            "relationships.json",
            "work_sessions.json",
            "import_batches.json",
        } <= names
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["format"] == "issuedeck.audit_bundle.v1"
        assert manifest["counts"]["items"] == 2

        items = json.loads(bundle.read("items.json"))
        first = next(item for item in items if item["local_id"] == "FEAT-0001")
        assert first["tags"] == ["hot"]
        assert first["external_links"][0]["link_type"] == "github_issue"
        assert first["events"][0]["event_type"] == "created"

        relationships = json.loads(bundle.read("relationships.json"))
        assert {
            (row["from_local_id"], row["to_local_id"], row["relation_type"])
            for row in relationships
        } == {
            ("FEAT-0001", "FEAT-0002", "blocks"),
            ("FEAT-0002", "FEAT-0001", "blocked_by"),
        }

        sessions = json.loads(bundle.read("work_sessions.json"))
        assert sessions[0]["agent_name"] == "codex"
        assert sessions[0]["metadata"] == {"ticket": "fixture"}
        assert sessions[0]["updates"][0]["update_type"] == "started"

        batches = json.loads(bundle.read("import_batches.json"))
        assert batches[0]["batch_tag"] == "csv-import-20260502"
        assert batches[0]["metadata"] == {"source": "fixture"}
