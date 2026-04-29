"""Pydantic DTOs for relationships."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

RelationType = Literal["blocks", "blocked_by", "related_to"]


class AddRelationshipRequest(BaseModel):
    to_local_id: str
    relation_type: RelationType


class RelationshipOut(BaseModel):
    rel_id: int
    from_local_id: str
    to_local_id: str
    relation_type: RelationType
