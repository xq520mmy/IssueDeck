"""FastAPI router for items."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response, status

from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.items.schemas import (
    BulkUpdateItemsRequest,
    BulkUpdateItemsResponse,
    CreateItemEventRequest,
    CreateItemRequest,
    ItemDetail,
    ItemEventOut,
    ItemListResponse,
    ItemSummary,
    ShipItemRequest,
    UpdateItemRequest,
)
from issuedeck.features.items.service import ItemService

router = APIRouter(prefix="/api/v1/projects/{project_key}/items", tags=["items"])

KIND_QUERY = Query(None)
STATUS_QUERY = Query(None, alias="status")
APPLIES_TO_QUERY = Query(None)
TAG_QUERY = Query(None)
RELATION_TYPE_QUERY = Query(None)


def _service(request: Request):
    session_factory = request.app.state.session_factory
    registry = request.app.state.registry
    webhook_dispatcher = getattr(request.app.state, "webhook_dispatcher", None)
    session = session_factory()
    return (
        ItemService(
            ItemRepo(session),
            registry,
            session,
            webhook_dispatcher=webhook_dispatcher,
        ),
        session,
    )


@router.post("", response_model=ItemSummary, status_code=status.HTTP_201_CREATED)
async def create_item(project_key: str, req: CreateItemRequest, request: Request):
    svc, session = _service(request)
    try:
        return await svc.create(project_key, req)
    finally:
        await session.close()


@router.get("", response_model=ItemListResponse)
async def list_items(
    project_key: str, request: Request,
    kind: list[str] | None = KIND_QUERY,
    status_: list[str] | None = STATUS_QUERY,
    applies_to: list[str] | None = APPLIES_TO_QUERY,
    shipped_in_branch: str | None = None,
    shipped_in_version: str | None = None,
    tag: list[str] | None = TAG_QUERY,
    relation_type: list[str] | None = RELATION_TYPE_QUERY,
    since: str | None = None,
    include_deleted: bool = False,
    only_deleted: bool = False,
    limit: int = 50,
    after: str | None = None,
):
    svc, session = _service(request)
    try:
        return await svc.list_items(
            project_key, kinds=kind, statuses=status_, applies_to=applies_to,
            shipped_in_branch=shipped_in_branch,
            shipped_in_version=shipped_in_version, tags=tag,
            relationship_types=relation_type, since=since,
            include_deleted=include_deleted, only_deleted=only_deleted,
            limit=limit, after=after,
        )
    finally:
        await session.close()


@router.post("/bulk", response_model=BulkUpdateItemsResponse)
async def bulk_update_items(
    project_key: str,
    req: BulkUpdateItemsRequest,
    request: Request,
):
    svc, session = _service(request)
    try:
        return await svc.bulk_update(project_key, req)
    finally:
        await session.close()


@router.get("/{local_id}", response_model=ItemDetail)
async def get_item(project_key: str, local_id: str, request: Request,
                   include_deleted: bool = False):
    svc, session = _service(request)
    try:
        return await svc.get(project_key, local_id, include_deleted=include_deleted)
    finally:
        await session.close()


@router.patch("/{local_id}", response_model=ItemSummary)
async def update_item(project_key: str, local_id: str,
                      req: UpdateItemRequest, request: Request):
    svc, session = _service(request)
    try:
        return await svc.update(project_key, local_id, req)
    finally:
        await session.close()


@router.post("/{local_id}/ship", response_model=ItemSummary)
async def ship_item(project_key: str, local_id: str,
                    req: ShipItemRequest, request: Request):
    svc, session = _service(request)
    try:
        return await svc.ship(project_key, local_id, req)
    finally:
        await session.close()


@router.post(
    "/{local_id}/events",
    response_model=ItemEventOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_item_event(
    project_key: str, local_id: str,
    req: CreateItemEventRequest, request: Request,
):
    svc, session = _service(request)
    try:
        return await svc.add_event(project_key, local_id, req)
    finally:
        await session.close()


@router.delete("/{local_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(project_key: str, local_id: str, request: Request,
                      reason: str = ""):
    svc, session = _service(request)
    try:
        await svc.soft_delete(project_key, local_id, reason=reason)
        return Response(status_code=204)
    finally:
        await session.close()


@router.post("/{local_id}/restore", response_model=ItemSummary)
async def restore_item(project_key: str, local_id: str, request: Request):
    svc, session = _service(request)
    try:
        return await svc.restore(project_key, local_id)
    finally:
        await session.close()
