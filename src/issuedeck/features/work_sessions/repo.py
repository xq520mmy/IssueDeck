"""Data access for agent work sessions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from issuedeck.features.items.models import Item, WorkSession, WorkSessionUpdate


class WorkSessionRepo:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def insert_session(
        self,
        *,
        project_key: str,
        item_pk: int,
        agent_name: str,
        goal: str,
        branch: str | None,
        metadata_json: str,
        created_at: str,
    ) -> WorkSession:
        session = WorkSession(
            project_key=project_key,
            item_pk=item_pk,
            agent_name=agent_name,
            status="active",
            goal=goal,
            summary="",
            branch=branch,
            started_at=created_at,
            updated_at=created_at,
            metadata_json=metadata_json,
        )
        self._s.add(session)
        await self._s.flush()
        return session

    async def append_update(
        self,
        *,
        session_id: int,
        update_type: str,
        message: str,
        metadata_json: str,
        created_at: str,
    ) -> WorkSessionUpdate:
        update = WorkSessionUpdate(
            session_id=session_id,
            update_type=update_type,
            message=message,
            metadata_json=metadata_json,
            created_at=created_at,
        )
        self._s.add(update)
        await self._s.flush()
        return update

    async def get(self, project_key: str, session_id: int) -> WorkSession | None:
        stmt = (
            select(WorkSession)
            .where(
                WorkSession.project_key == project_key,
                WorkSession.id == session_id,
            )
            .execution_options(populate_existing=True)
            .options(
                selectinload(WorkSession.item),
                selectinload(WorkSession.updates),
            )
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def list_sessions(
        self,
        project_key: str,
        *,
        statuses: list[str] | None = None,
        agent_name: str | None = None,
        local_id: str | None = None,
        limit: int = 50,
    ) -> list[WorkSession]:
        stmt = select(WorkSession).where(WorkSession.project_key == project_key)
        if statuses:
            stmt = stmt.where(WorkSession.status.in_(statuses))
        if agent_name:
            stmt = stmt.where(WorkSession.agent_name == agent_name)
        if local_id:
            item_pk = select(Item.pk).where(
                Item.project_key == project_key,
                Item.local_id == local_id,
            )
            stmt = stmt.where(WorkSession.item_pk.in_(item_pk))
        stmt = (
            stmt
            .execution_options(populate_existing=True)
            .options(
                selectinload(WorkSession.item),
                selectinload(WorkSession.updates),
            )
            .order_by(WorkSession.updated_at.desc(), WorkSession.id.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())
