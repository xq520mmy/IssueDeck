"""Pydantic DTOs for agent work sessions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

WorkSessionStatus = Literal["active", "paused", "completed", "canceled"]
OpenWorkSessionStatus = Literal["active", "paused"]
FinishedWorkSessionStatus = Literal["completed", "canceled"]


class CreateWorkSessionRequest(BaseModel):
    local_id: str = Field(min_length=1, max_length=64)
    agent_name: str = Field(min_length=1, max_length=128)
    goal: str = Field(min_length=1, max_length=5000)
    branch: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateWorkSessionRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    update_type: str = Field(
        default="progress",
        min_length=1,
        max_length=32,
        pattern=r"^[a-z0-9_:-]+$",
    )
    status: OpenWorkSessionStatus | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinishWorkSessionRequest(BaseModel):
    status: FinishedWorkSessionStatus = "completed"
    summary: str = Field(default="", max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkSessionUpdateOut(BaseModel):
    id: int
    update_type: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class WorkSessionSummary(BaseModel):
    id: int
    project_key: str
    local_id: str | None = None
    item_title: str | None = None
    agent_name: str
    status: WorkSessionStatus
    goal: str
    summary: str
    branch: str | None = None
    started_at: str
    updated_at: str
    ended_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    update_count: int


class WorkSessionDetail(WorkSessionSummary):
    updates: list[WorkSessionUpdateOut] = Field(default_factory=list)


class WorkSessionListResponse(BaseModel):
    sessions: list[WorkSessionSummary]
    limit: int

