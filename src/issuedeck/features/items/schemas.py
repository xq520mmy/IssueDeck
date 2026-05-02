"""Pydantic DTOs for the items feature.

Service layer returns these (never ORM instances), and routes declare them as
response models. Request models validate shape; business rules like
"kind must exist in project config" are enforced in the service layer with
InvalidKind / InvalidStatus exceptions, not here.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from issuedeck.features.items.external_links import normalize_external_link_payload


class ExternalLinkInput(BaseModel):
    link_type: Literal["github_issue", "github_pr", "github_commit", "other"] = "other"
    url: str = Field(min_length=1, max_length=2048)
    label: str | None = Field(default=None, max_length=160)

    @model_validator(mode="before")
    @classmethod
    def _infer_github_url(cls, data: object) -> object:
        if isinstance(data, dict):
            return normalize_external_link_payload(data)
        return data


class CreateItemRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=500)
    body: str = ""
    applies_to: list[str] | None = None
    tags: list[str] = []
    external_links: list[ExternalLinkInput] = []
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class UpdateItemRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = None
    append_body: str | None = None
    status: str | None = None
    applies_to: list[str] | None = None
    tags: list[str] | None = None
    external_links: list[ExternalLinkInput] | None = None
    custom_fields: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _checks(self) -> UpdateItemRequest:
        if self.body is not None and self.append_body is not None:
            raise ValueError("body and append_body are mutually exclusive")
        if self.status == "done":
            raise ValueError(
                "cannot set status=done via update; use ship to bind a version"
            )
        if self.applies_to is not None and not self.applies_to:
            raise ValueError("applies_to cannot be empty — must target at least one branch")
        return self


class BulkUpdateItemsRequest(BaseModel):
    local_ids: list[str] = Field(min_length=1, max_length=500)
    action: Literal["update", "delete", "restore"] = "update"
    kind: str | None = Field(default=None, min_length=1, max_length=64)
    status: str | None = None
    applies_to: list[str] | None = None
    tags: list[str] | None = None
    tag_mode: Literal["add", "remove", "replace"] = "add"
    custom_fields: dict[str, Any] | None = None
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _checks(self) -> BulkUpdateItemsRequest:
        self.local_ids = _dedupe_clean(self.local_ids)
        if not self.local_ids:
            raise ValueError("local_ids cannot be empty")
        if self.applies_to is not None:
            self.applies_to = _dedupe_clean(self.applies_to)
            if not self.applies_to:
                raise ValueError("applies_to cannot be empty — must target at least one branch")
        if self.tags is not None:
            self.tags = _dedupe_clean(self.tags)
        if self.custom_fields is not None and not self.custom_fields:
            self.custom_fields = None
        if self.status == "done":
            raise ValueError(
                "cannot set status=done via update; use ship to bind a version"
            )
        if self.action == "update" and not any(
            value is not None
            for value in (
                self.kind,
                self.status,
                self.applies_to,
                self.tags,
                self.custom_fields,
            )
        ):
            raise ValueError("bulk update requires at least one field to change")
        return self


class ShipItemRequest(BaseModel):
    branch: str = Field(min_length=1)
    version: str = Field(min_length=1, max_length=64)
    commits: list[str] = []


class CreateItemEventRequest(BaseModel):
    event_type: str = Field(
        default="comment",
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_:-]+$",
    )
    actor_type: Literal["human", "agent", "system"] = "human"
    actor_name: str = Field(default="dashboard", min_length=1, max_length=128)
    body: str = Field(min_length=1, max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ItemEventOut(BaseModel):
    id: int
    event_type: str
    actor_type: Literal["human", "agent", "system"]
    actor_name: str
    body: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ExternalLinkOut(BaseModel):
    id: int
    link_type: Literal["github_issue", "github_pr", "github_commit", "other"]
    label: str | None = None
    url: str
    created_at: str


class ShipRecordOut(BaseModel):
    branch_key: str
    version: str
    shipped_at: str
    commits: list[str] = []


class RelationshipOut(BaseModel):
    rel_id: int
    to_local_id: str
    relation_type: Literal["blocks", "blocked_by", "related_to"]


class ItemSummary(BaseModel):
    project_key: str
    local_id: str
    kind: str
    status: str
    title: str
    body_preview: str
    tags: list[str]
    applies_to: list[str]
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    external_links: list[ExternalLinkOut] = []
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class ItemDetail(BaseModel):
    project_key: str
    local_id: str
    kind: str
    status: str
    title: str
    body: str
    tags: list[str]
    applies_to: list[str]
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    external_links: list[ExternalLinkOut] = []
    created_at: str
    updated_at: str
    deleted_at: str | None = None
    ship_records: list[ShipRecordOut] = []
    relationships: list[RelationshipOut] = []
    events: list[ItemEventOut] = []


class ItemListResponse(BaseModel):
    items: list[ItemSummary]
    next_cursor: str | None = None
    limit: int


class BulkUpdateItemsResponse(BaseModel):
    action: Literal["update", "delete", "restore"]
    requested_count: int
    updated_count: int
    items: list[ItemSummary] = []


def _dedupe_clean(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        clean = value.strip()
        if clean and clean not in result:
            result.append(clean)
    return result
