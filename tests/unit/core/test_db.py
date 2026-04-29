from sqlalchemy import text

from issuedeck.core.db import make_engine, make_session_factory


async def test_in_memory_engine_executes_select():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
    finally:
        await engine.dispose()


async def test_session_factory_yields_session():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
    finally:
        await engine.dispose()


async def test_pragmas_applied_on_file_backed_engine(tmp_path):
    db_path = tmp_path / "t.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    try:
        async with engine.connect() as conn:
            jm = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
            assert jm.lower() == "wal"
            fk = (await conn.execute(text("PRAGMA foreign_keys"))).scalar()
            assert fk == 1
    finally:
        await engine.dispose()
