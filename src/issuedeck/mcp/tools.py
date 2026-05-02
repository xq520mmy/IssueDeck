"""MCP tool functions. Thin wrappers calling IssueDeckClient."""
from __future__ import annotations

from typing import Any

from issuedeck.mcp.client import get_client


def _drop_none(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


async def list_projects() -> dict[str, Any]:
    """List every configured issuedeck project."""
    return await get_client().list_projects()


async def get_project_config(project_key: str) -> dict[str, Any]:
    """Return the kinds, statuses, tags and applies_to values for a project."""
    return await get_client().get_project_config(project_key)


async def create_item(
    project_key: str,
    kind: str,
    title: str,
    body: str = "",
    tags: list[str] | None = None,
    applies_to: list[str] | None = None,
    custom_fields: dict[str, Any] | None = None,
    external_links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a new tracker item. Returns the full item with its local_id."""
    payload = _drop_none({
        "kind": kind,
        "title": title,
        "body": body,
        "tags": tags,
        "applies_to": applies_to,
        "custom_fields": custom_fields,
        "external_links": external_links,
    })
    return await get_client().create_item(project_key, payload)


async def update_item(
    project_key: str,
    local_id: str,
    title: str | None = None,
    body: str | None = None,
    append_body: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
    applies_to: list[str] | None = None,
    custom_fields: dict[str, Any] | None = None,
    external_links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Partial update of an item. Pass body OR append_body, not both."""
    payload = _drop_none({
        "title": title,
        "body": body,
        "append_body": append_body,
        "status": status,
        "tags": tags,
        "applies_to": applies_to,
        "custom_fields": custom_fields,
        "external_links": external_links,
    })
    return await get_client().update_item(project_key, local_id, payload)


async def bulk_update_items(
    project_key: str,
    local_ids: list[str],
    action: str = "update",
    kind: str | None = None,
    status: str | None = None,
    applies_to: list[str] | None = None,
    tags: list[str] | None = None,
    tag_mode: str = "add",
    custom_fields: dict[str, Any] | None = None,
    reason: str = "mcp bulk update",
) -> dict[str, Any]:
    """Update, delete, or restore multiple items by local_id."""
    payload = _drop_none({
        "local_ids": local_ids,
        "action": action,
        "kind": kind,
        "status": status,
        "applies_to": applies_to,
        "tags": tags,
        "tag_mode": tag_mode,
        "custom_fields": custom_fields,
        "reason": reason,
    })
    return await get_client().bulk_update_items(project_key, payload)


async def ship_item(
    project_key: str,
    local_id: str,
    branch: str,
    version: str,
    commits: list[str] | None = None,
) -> dict[str, Any]:
    """Mark an item as shipped on a given branch at a given version."""
    payload = _drop_none({
        "branch": branch,
        "version": version,
        "commits": commits,
    })
    return await get_client().ship_item(project_key, local_id, payload)


async def append_item_event(
    project_key: str,
    local_id: str,
    body: str,
    event_type: str = "comment",
    actor_type: str = "agent",
    actor_name: str = "agent",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append an activity timeline event or comment to an item."""
    payload = _drop_none({
        "event_type": event_type,
        "actor_type": actor_type,
        "actor_name": actor_name,
        "body": body,
        "metadata": metadata,
    })
    return await get_client().create_item_event(project_key, local_id, payload)


async def delete_item(project_key: str, local_id: str) -> dict[str, Any]:
    """Soft-delete an item."""
    return await get_client().delete_item(project_key, local_id)


async def get_item(project_key: str, local_id: str) -> dict[str, Any]:
    """Fetch a single item with relationships and ship history."""
    return await get_client().get_item(project_key, local_id)


async def list_items(
    project_key: str,
    status: str | None = None,
    kind: str | None = None,
    tag: list[str] | None = None,
    applies_to: str | None = None,
    relation_type: str | None = None,
    custom_field: list[str] | None = None,
    shipped_in_branch: str | None = None,
    since: str | None = None,
    include_deleted: bool = False,
    only_deleted: bool = False,
    after: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List items with filters.

    custom_field entries use FIELD=VALUE, FIELD>=VALUE, or FIELD:missing syntax.
    """
    params: dict[str, Any] = _drop_none({
        "status": status,
        "kind": kind,
        "applies_to": applies_to,
        "relation_type": relation_type,
        "shipped_in_branch": shipped_in_branch,
        "since": since,
        "after": after,
    })
    params["limit"] = limit
    if include_deleted:
        params["include_deleted"] = "true"
    if only_deleted:
        params["only_deleted"] = "true"
    if tag:
        params["tag"] = tag
    if custom_field:
        params["custom_field"] = custom_field
    return await get_client().list_items(project_key, params)


async def search_items(
    project_key: str,
    q: str,
    limit: int = 20,
) -> dict[str, Any]:
    """Full-text search items using FTS5 MATCH syntax."""
    return await get_client().search_items(
        project_key, {"q": q, "limit": limit},
    )


async def add_relationship(
    project_key: str,
    from_local_id: str,
    to_local_id: str,
    relation_type: str,
) -> dict[str, Any]:
    """Create a relationship between two items. relation_type in {blocks, related_to}."""
    return await get_client().add_relationship(
        project_key,
        from_local_id,
        {
            "to_local_id": to_local_id,
            "relation_type": relation_type,
        },
    )


async def remove_relationship(
    project_key: str,
    rel_id: int,
) -> dict[str, Any]:
    """Delete a relationship and its bidirectional inverse."""
    return await get_client().remove_relationship(project_key, rel_id)


async def start_work_session(
    project_key: str,
    local_id: str,
    agent_name: str,
    goal: str,
    branch: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Start an agent work session on a tracked item."""
    payload = _drop_none({
        "local_id": local_id,
        "agent_name": agent_name,
        "goal": goal,
        "branch": branch,
        "metadata": metadata,
    })
    return await get_client().start_work_session(project_key, payload)


async def list_work_sessions(
    project_key: str,
    status: str | None = None,
    agent_name: str | None = None,
    local_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List agent work sessions, optionally filtered by status, agent, or item."""
    params = _drop_none({
        "status": status,
        "agent_name": agent_name,
        "local_id": local_id,
    })
    params["limit"] = limit
    return await get_client().list_work_sessions(project_key, params)


async def get_work_session(
    project_key: str,
    session_id: int,
) -> dict[str, Any]:
    """Fetch a single agent work session with progress updates."""
    return await get_client().get_work_session(project_key, session_id)


async def update_work_session(
    project_key: str,
    session_id: int,
    message: str,
    update_type: str = "progress",
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append progress to an active agent work session."""
    payload = _drop_none({
        "message": message,
        "update_type": update_type,
        "status": status,
        "metadata": metadata,
    })
    return await get_client().update_work_session(project_key, session_id, payload)


async def finish_work_session(
    project_key: str,
    session_id: int,
    status: str = "completed",
    summary: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mark an agent work session as completed or canceled."""
    payload = _drop_none({
        "status": status,
        "summary": summary,
        "metadata": metadata,
    })
    return await get_client().finish_work_session(project_key, session_id, payload)
