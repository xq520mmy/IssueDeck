"""FastAPI router for relationships."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.relationships.repo import RelationshipRepo
from issuedeck.features.relationships.schemas import (
    AddRelationshipRequest,
    RelationshipOut,
)
from issuedeck.features.relationships.service import RelationshipService

router = APIRouter(prefix="/api/v1/projects/{project_key}", tags=["relationships"])


def _service(request: Request):
    session = request.app.state.session_factory()
    registry = request.app.state.registry
    return RelationshipService(
        RelationshipRepo(session), ItemRepo(session), registry, session,
    ), session


@router.post(
    "/items/{local_id}/relationships",
    response_model=RelationshipOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_relationship(
    project_key: str, local_id: str,
    req: AddRelationshipRequest, request: Request,
):
    svc, session = _service(request)
    try:
        return await svc.add(
            project_key, local_id,
            to_local_id=req.to_local_id, relation_type=req.relation_type,
        )
    finally:
        await session.close()


@router.delete(
    "/relationships/{rel_id}", status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_relationship(project_key: str, rel_id: int, request: Request):
    svc, session = _service(request)
    try:
        await svc.remove(rel_id)
        return Response(status_code=204)
    finally:
        await session.close()
