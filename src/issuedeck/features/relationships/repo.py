"""Data access for item_relationships."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from issuedeck.features.items.models import ItemRelationship


class RelationshipRepo:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def add(
        self, *, from_pk: int, to_pk: int, relation_type: str, created_at: str,
    ) -> ItemRelationship:
        row = ItemRelationship(
            from_item_pk=from_pk, to_item_pk=to_pk,
            relation_type=relation_type, created_at=created_at,
        )
        self._s.add(row)
        await self._s.flush()
        return row

    async def find_exact(
        self, *, from_pk: int, to_pk: int, relation_type: str,
    ) -> ItemRelationship | None:
        stmt = select(ItemRelationship).where(
            ItemRelationship.from_item_pk == from_pk,
            ItemRelationship.to_item_pk == to_pk,
            ItemRelationship.relation_type == relation_type,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def get(self, rel_id: int) -> ItemRelationship | None:
        return (await self._s.execute(
            select(ItemRelationship).where(ItemRelationship.id == rel_id)
        )).scalar_one_or_none()

    async def delete_pair(
        self, *, from_pk: int, to_pk: int, relation_type: str,
    ) -> None:
        inverse = _inverse_type(relation_type)
        for f, t, rt in [(from_pk, to_pk, relation_type),
                         (to_pk, from_pk, inverse)]:
            row = await self.find_exact(from_pk=f, to_pk=t, relation_type=rt)
            if row is not None:
                await self._s.delete(row)
        await self._s.flush()


def _inverse_type(relation_type: str) -> str:
    return {"blocks": "blocked_by", "blocked_by": "blocks",
            "related_to": "related_to"}[relation_type]
