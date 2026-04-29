"""Async SQLAlchemy engine + session factory.

Binds a `connect` event listener that applies per-connection PRAGMAs:

- `journal_mode=WAL` — concurrent readers while a single writer holds the write lock
- `foreign_keys=ON` — SQLite defaults to off, but our schema relies on FK cascades
- `busy_timeout` — wait out contention rather than raising immediately
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def make_engine(url: str, *, busy_timeout_ms: int = 5000) -> AsyncEngine:
    engine = create_async_engine(url, echo=False, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _conn_record):
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        finally:
            cur.close()

    return engine


def make_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
