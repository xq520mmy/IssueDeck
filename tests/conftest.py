"""Global pytest fixtures. Populated in later tasks."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def migrated_engine(tmp_path):
    """File-backed SQLite with the full Alembic head schema applied.

    FTS5 triggers are only created by the migration (not by Base.metadata),
    so tests that rely on search must use this fixture.
    """
    db_path = tmp_path / "test.db"
    cfg = Config(str(Path.cwd() / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def migrated_session(migrated_engine):
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    async with Session() as s:
        yield s
