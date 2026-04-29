"""SearchService — FTS5 search for items."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from issuedeck.core.config import ConfigRegistry
from issuedeck.core.pagination import decode_cursor, encode_cursor
from issuedeck.features.items.schemas import ItemListResponse, ItemSummary
from issuedeck.features.search.repo import SearchRepo


def _preview(body: str, n: int = 200) -> str:
    return (body[:n] + "…") if len(body) > n else body


class SearchService:
    def __init__(
        self, repo: SearchRepo, registry: ConfigRegistry, session: AsyncSession,
    ):
        self._repo = repo
        self._reg = registry
        self._s = session

    async def search(
        self, project_key: str, query: str, *,
        limit: int = 50, after: str | None = None,
    ) -> ItemListResponse:
        self._reg.project(project_key)
        limit = max(1, min(limit, 500))

        after_ts, after_pk = (None, None)
        if after:
            c = decode_cursor(after)
            after_ts, after_pk = c.updated_at, c.pk

        rows = await self._repo.match(
            project_key, query, limit=limit + 1,
            after_updated_at=after_ts, after_pk=after_pk,
        )
        has_more = len(rows) > limit
        rows = rows[:limit]

        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = encode_cursor(last.updated_at, last.pk)

        summaries = [
            ItemSummary(
                project_key=i.project_key, local_id=i.local_id,
                kind=i.kind, status=i.status, title=i.title,
                body_preview=_preview(i.body or ""),
                tags=[t.tag for t in i.tags],
                applies_to=[a.branch_key for a in i.applies_to],
                created_at=i.created_at, updated_at=i.updated_at,
                deleted_at=i.deleted_at,
            )
            for i in rows
        ]
        return ItemListResponse(items=summaries, next_cursor=next_cursor, limit=limit)
