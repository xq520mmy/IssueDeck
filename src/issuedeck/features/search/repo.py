"""SearchRepo — thin wrapper over FTS5 MATCH queries."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from issuedeck.features.items.models import Item


class SearchRepo:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def match(
        self, project_key: str, query: str, *, limit: int,
        after_updated_at: str | None = None, after_pk: int | None = None,
    ) -> list[Item]:
        sql = text(
            """
            SELECT i.pk FROM items i
            JOIN items_fts f ON f.rowid = i.pk
            WHERE items_fts MATCH :q
              AND i.project_key = :pk
              AND i.deleted_at IS NULL
              AND (:after_ts IS NULL OR (i.updated_at, i.pk) < (:after_ts, :after_pk))
            ORDER BY i.updated_at DESC, i.pk DESC
            LIMIT :limit
            """
        )
        result = await self._s.execute(sql, {
            "q": query, "pk": project_key,
            "after_ts": after_updated_at, "after_pk": after_pk,
            "limit": limit,
        })
        pks = [r[0] for r in result.all()]
        if not pks:
            return []
        items = (await self._s.execute(
            select(Item)
            .where(Item.pk.in_(pks))
            .options(selectinload(Item.tags), selectinload(Item.applies_to))
        )).scalars().all()
        order = {pk: i for i, pk in enumerate(pks)}
        return sorted(items, key=lambda x: order[x.pk])
