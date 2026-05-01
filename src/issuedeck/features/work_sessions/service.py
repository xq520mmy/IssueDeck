"""Business logic for agent work sessions."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from issuedeck.core.config import ConfigRegistry
from issuedeck.core.errors import InvalidTransition, ItemNotFound, WorkSessionNotFound
from issuedeck.features.items.models import Item, WorkSession, WorkSessionUpdate
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.work_sessions.repo import WorkSessionRepo
from issuedeck.features.work_sessions.schemas import (
    CreateWorkSessionRequest,
    FinishWorkSessionRequest,
    UpdateWorkSessionRequest,
    WorkSessionDetail,
    WorkSessionListResponse,
    WorkSessionSummary,
    WorkSessionUpdateOut,
)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _metadata_json(metadata: dict | None) -> str:
    return json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)


def _metadata(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"raw": raw}
    return value if isinstance(value, dict) else {"value": value}


class WorkSessionService:
    def __init__(
        self,
        repo: WorkSessionRepo,
        item_repo: ItemRepo,
        registry: ConfigRegistry,
        session: AsyncSession,
    ):
        self._repo = repo
        self._item_repo = item_repo
        self._registry = registry
        self._s = session

    async def start(
        self,
        project_key: str,
        req: CreateWorkSessionRequest,
    ) -> WorkSessionDetail:
        self._registry.project(project_key)
        if req.branch is not None:
            self._registry.validate_branch(project_key, req.branch)
        item = await self._load_item(project_key, req.local_id)
        now = _iso_now()
        session = await self._repo.insert_session(
            project_key=project_key,
            item_pk=item.pk,
            agent_name=req.agent_name,
            goal=req.goal,
            branch=req.branch,
            metadata_json=_metadata_json(req.metadata),
            created_at=now,
        )
        await self._repo.append_update(
            session_id=session.id,
            update_type="started",
            message=req.goal,
            metadata_json=_metadata_json(req.metadata),
            created_at=now,
        )
        await self._record_item_event(
            item,
            event_type="work_session_started",
            actor_name=req.agent_name,
            body=f"Started work session: {req.goal}",
            metadata={
                "session_id": session.id,
                "status": "active",
                "branch": req.branch,
            },
            created_at=now,
        )
        item.updated_at = now
        await self._s.commit()
        refreshed = await self._repo.get(project_key, session.id)
        return self._to_detail(refreshed)

    async def update(
        self,
        project_key: str,
        session_id: int,
        req: UpdateWorkSessionRequest,
    ) -> WorkSessionDetail:
        session = await self._load_session(project_key, session_id)
        if session.status in {"completed", "canceled"}:
            raise InvalidTransition(
                f"work session {session_id} is already {session.status}",
                details={"session_id": session_id, "status": session.status},
            )

        now = _iso_now()
        previous_status = session.status
        if req.status is not None:
            session.status = req.status
        session.updated_at = now
        await self._repo.append_update(
            session_id=session.id,
            update_type=req.update_type,
            message=req.message,
            metadata_json=_metadata_json(req.metadata),
            created_at=now,
        )
        if session.item is not None:
            session.item.updated_at = now
            event_type = "work_session_updated"
            if req.status == "paused" and previous_status != "paused":
                event_type = "work_session_paused"
            elif req.status == "active" and previous_status == "paused":
                event_type = "work_session_resumed"
            await self._record_item_event(
                session.item,
                event_type=event_type,
                actor_name=session.agent_name,
                body=req.message,
                metadata={
                    "session_id": session.id,
                    "status": session.status,
                    "update_type": req.update_type,
                },
                created_at=now,
            )
        await self._s.commit()
        refreshed = await self._repo.get(project_key, session_id)
        return self._to_detail(refreshed)

    async def finish(
        self,
        project_key: str,
        session_id: int,
        req: FinishWorkSessionRequest,
    ) -> WorkSessionDetail:
        session = await self._load_session(project_key, session_id)
        if session.status in {"completed", "canceled"}:
            raise InvalidTransition(
                f"work session {session_id} is already {session.status}",
                details={"session_id": session_id, "status": session.status},
            )

        now = _iso_now()
        summary = req.summary.strip()
        message = summary or f"{req.status.title()} work session."
        session.status = req.status
        session.summary = summary
        session.ended_at = now
        session.updated_at = now
        await self._repo.append_update(
            session_id=session.id,
            update_type=req.status,
            message=message,
            metadata_json=_metadata_json(req.metadata),
            created_at=now,
        )
        if session.item is not None:
            session.item.updated_at = now
            await self._record_item_event(
                session.item,
                event_type=f"work_session_{req.status}",
                actor_name=session.agent_name,
                body=message,
                metadata={
                    "session_id": session.id,
                    "status": req.status,
                },
                created_at=now,
            )
        await self._s.commit()
        refreshed = await self._repo.get(project_key, session_id)
        return self._to_detail(refreshed)

    async def get(self, project_key: str, session_id: int) -> WorkSessionDetail:
        session = await self._load_session(project_key, session_id)
        return self._to_detail(session)

    async def list_sessions(
        self,
        project_key: str,
        *,
        statuses: list[str] | None = None,
        agent_name: str | None = None,
        local_id: str | None = None,
        limit: int = 50,
    ) -> WorkSessionListResponse:
        self._registry.project(project_key)
        limit = max(1, min(limit, 200))
        if local_id is not None:
            await self._load_item(project_key, local_id)
        rows = await self._repo.list_sessions(
            project_key,
            statuses=statuses,
            agent_name=agent_name,
            local_id=local_id,
            limit=limit,
        )
        return WorkSessionListResponse(
            sessions=[self._to_summary(row) for row in rows],
            limit=limit,
        )

    async def _load_item(self, project_key: str, local_id: str) -> Item:
        item = await self._item_repo.get_by_local_id(project_key, local_id)
        if item is None:
            raise ItemNotFound(
                f"item {local_id} not found in project '{project_key}'",
                details={"project_key": project_key, "local_id": local_id},
            )
        return item

    async def _load_session(self, project_key: str, session_id: int) -> WorkSession:
        session = await self._repo.get(project_key, session_id)
        if session is None:
            raise WorkSessionNotFound(
                f"work session {session_id} not found in project '{project_key}'",
                details={"project_key": project_key, "session_id": session_id},
            )
        return session

    async def _record_item_event(
        self,
        item: Item,
        *,
        event_type: str,
        actor_name: str,
        body: str,
        metadata: dict,
        created_at: str,
    ) -> None:
        await self._item_repo.add_event(
            item_pk=item.pk,
            event_type=event_type,
            actor_type="agent",
            actor_name=actor_name,
            body=body,
            metadata_json=_metadata_json(metadata),
            created_at=created_at,
        )

    def _to_summary(self, session: WorkSession) -> WorkSessionSummary:
        item = session.item
        return WorkSessionSummary(
            id=session.id,
            project_key=session.project_key,
            local_id=item.local_id if item is not None else None,
            item_title=item.title if item is not None else None,
            agent_name=session.agent_name,
            status=session.status,
            goal=session.goal,
            summary=session.summary or "",
            branch=session.branch,
            started_at=session.started_at,
            updated_at=session.updated_at,
            ended_at=session.ended_at,
            metadata=_metadata(session.metadata_json),
            update_count=len(session.updates),
        )

    def _to_detail(self, session: WorkSession | None) -> WorkSessionDetail:
        if session is None:
            raise WorkSessionNotFound("work session not found")
        summary = self._to_summary(session)
        return WorkSessionDetail(
            **summary.model_dump(),
            updates=[self._to_update(update) for update in session.updates],
        )

    def _to_update(self, update: WorkSessionUpdate) -> WorkSessionUpdateOut:
        return WorkSessionUpdateOut(
            id=update.id,
            update_type=update.update_type,
            message=update.message,
            metadata=_metadata(update.metadata_json),
            created_at=update.created_at,
        )

