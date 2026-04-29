"""RelationshipService — enforces bidirectional invariant."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from issuedeck.core.config import ConfigRegistry
from issuedeck.core.errors import (
    ItemNotFound,
    RelationshipDuplicate,
    RelationshipSelfLoop,
)
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.relationships.repo import RelationshipRepo, _inverse_type
from issuedeck.features.relationships.schemas import RelationshipOut


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


class RelationshipService:
    def __init__(
        self, rel_repo: RelationshipRepo, item_repo: ItemRepo,
        registry: ConfigRegistry, session: AsyncSession,
    ):
        self._rr = rel_repo
        self._ir = item_repo
        self._reg = registry
        self._s = session

    async def add(
        self, project_key: str, from_local_id: str, *,
        to_local_id: str, relation_type: str,
    ) -> RelationshipOut:
        self._reg.project(project_key)

        if from_local_id == to_local_id:
            raise RelationshipSelfLoop(
                f"cannot relate {from_local_id} to itself",
                details={"local_id": from_local_id},
            )

        from_item = await self._ir.get_by_local_id(project_key, from_local_id)
        if from_item is None:
            raise ItemNotFound(f"item {from_local_id} not found",
                               details={"project_key": project_key,
                                        "local_id": from_local_id})
        to_item = await self._ir.get_by_local_id(project_key, to_local_id)
        if to_item is None:
            raise ItemNotFound(f"item {to_local_id} not found",
                               details={"project_key": project_key,
                                        "local_id": to_local_id})

        if await self._rr.find_exact(
            from_pk=from_item.pk, to_pk=to_item.pk, relation_type=relation_type,
        ):
            raise RelationshipDuplicate(
                f"relationship already exists: "
                f"{from_local_id} -{relation_type}-> {to_local_id}",
                details={"from": from_local_id, "to": to_local_id,
                         "relation_type": relation_type},
            )

        now = _iso_now()
        forward = await self._rr.add(
            from_pk=from_item.pk, to_pk=to_item.pk,
            relation_type=relation_type, created_at=now,
        )
        await self._rr.add(
            from_pk=to_item.pk, to_pk=from_item.pk,
            relation_type=_inverse_type(relation_type), created_at=now,
        )
        await self._s.commit()
        return RelationshipOut(
            rel_id=forward.id, from_local_id=from_local_id,
            to_local_id=to_local_id, relation_type=relation_type,
        )

    async def remove(self, rel_id: int) -> None:
        row = await self._rr.get(rel_id)
        if row is None:
            raise ItemNotFound(f"relationship {rel_id} not found",
                               details={"rel_id": rel_id})
        await self._rr.delete_pair(
            from_pk=row.from_item_pk, to_pk=row.to_item_pk,
            relation_type=row.relation_type,
        )
        await self._s.commit()
