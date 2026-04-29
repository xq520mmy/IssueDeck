"""FastAPI router for projects."""

from __future__ import annotations

from fastapi import APIRouter, Request

from issuedeck.features.projects.schemas import ProjectDetail, ProjectList
from issuedeck.features.projects.service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", response_model=ProjectList)
async def list_projects(request: Request):
    session = request.app.state.session_factory()
    try:
        return await ProjectService(request.app.state.registry, session).list_projects()
    finally:
        await session.close()


@router.get("/{key}", response_model=ProjectDetail)
async def get_project(key: str, request: Request):
    session = request.app.state.session_factory()
    try:
        return ProjectService(request.app.state.registry, session).get_project(key)
    finally:
        await session.close()
