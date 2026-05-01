"""FastAPI router for agent work sessions."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, status

from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.work_sessions.repo import WorkSessionRepo
from issuedeck.features.work_sessions.schemas import (
    CreateWorkSessionRequest,
    FinishWorkSessionRequest,
    UpdateWorkSessionRequest,
    WorkSessionDetail,
    WorkSessionListResponse,
)
from issuedeck.features.work_sessions.service import WorkSessionService

router = APIRouter(
    prefix="/api/v1/projects/{project_key}/work-sessions",
    tags=["work-sessions"],
)

STATUS_QUERY = Query(None, alias="status")


def _service(request: Request):
    session_factory = request.app.state.session_factory
    registry = request.app.state.registry
    session = session_factory()
    return (
        WorkSessionService(
            WorkSessionRepo(session),
            ItemRepo(session),
            registry,
            session,
        ),
        session,
    )


@router.post("", response_model=WorkSessionDetail, status_code=status.HTTP_201_CREATED)
async def start_work_session(
    project_key: str,
    req: CreateWorkSessionRequest,
    request: Request,
):
    svc, session = _service(request)
    try:
        return await svc.start(project_key, req)
    finally:
        await session.close()


@router.get("", response_model=WorkSessionListResponse)
async def list_work_sessions(
    project_key: str,
    request: Request,
    status_: list[str] | None = STATUS_QUERY,
    agent_name: str | None = None,
    local_id: str | None = None,
    limit: int = 50,
):
    svc, session = _service(request)
    try:
        return await svc.list_sessions(
            project_key,
            statuses=status_,
            agent_name=agent_name,
            local_id=local_id,
            limit=limit,
        )
    finally:
        await session.close()


@router.get("/{session_id}", response_model=WorkSessionDetail)
async def get_work_session(
    project_key: str,
    session_id: int,
    request: Request,
):
    svc, session = _service(request)
    try:
        return await svc.get(project_key, session_id)
    finally:
        await session.close()


@router.post("/{session_id}/updates", response_model=WorkSessionDetail)
async def update_work_session(
    project_key: str,
    session_id: int,
    req: UpdateWorkSessionRequest,
    request: Request,
):
    svc, session = _service(request)
    try:
        return await svc.update(project_key, session_id, req)
    finally:
        await session.close()


@router.post("/{session_id}/finish", response_model=WorkSessionDetail)
async def finish_work_session(
    project_key: str,
    session_id: int,
    req: FinishWorkSessionRequest,
    request: Request,
):
    svc, session = _service(request)
    try:
        return await svc.finish(project_key, session_id, req)
    finally:
        await session.close()
