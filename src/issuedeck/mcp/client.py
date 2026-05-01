"""Thin httpx wrapper used by the MCP stdio process."""
from __future__ import annotations

import os
from typing import Any

import httpx

from issuedeck.core.errors import (
    ConfigError,
    InvalidBranch,
    InvalidKind,
    InvalidStatus,
    InvalidTransition,
    IssueDeckError,
    ItemNotFound,
    ProjectNotFound,
    RelationshipDuplicate,
    RelationshipSelfLoop,
    ShipRequiresBranchConfig,
    Unauthorized,
    WorkSessionNotFound,
)

_ERROR_MAP: dict[str, type[IssueDeckError]] = {
    ConfigError.code: ConfigError,
    ProjectNotFound.code: ProjectNotFound,
    ItemNotFound.code: ItemNotFound,
    InvalidKind.code: InvalidKind,
    InvalidStatus.code: InvalidStatus,
    InvalidBranch.code: InvalidBranch,
    InvalidTransition.code: InvalidTransition,
    ShipRequiresBranchConfig.code: ShipRequiresBranchConfig,
    RelationshipSelfLoop.code: RelationshipSelfLoop,
    RelationshipDuplicate.code: RelationshipDuplicate,
    Unauthorized.code: Unauthorized,
    WorkSessionNotFound.code: WorkSessionNotFound,
}


def _raise_for_error(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    try:
        envelope = response.json().get("error", {})
    except Exception:
        envelope = {}
    code = envelope.get("code", "internal_error")
    message = envelope.get("message", response.text or "issuedeck error")
    exc_cls = _ERROR_MAP.get(code, IssueDeckError)
    raise exc_cls(message)


class IssueDeckClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        headers = {"Authorization": f"Bearer {token}"}
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(
        self, method: str, path: str, **kwargs: Any,
    ) -> dict[str, Any]:
        r = await self._http.request(method, path, **kwargs)
        _raise_for_error(r)
        if r.status_code == 204 or not r.content:
            return {}
        return r.json()

    async def list_projects(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/projects")

    async def get_project_config(self, key: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/projects/{key}")

    async def create_item(self, key: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/api/v1/projects/{key}/items", json=body)

    async def update_item(
        self, key: str, local_id: str, body: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH", f"/api/v1/projects/{key}/items/{local_id}", json=body,
        )

    async def ship_item(
        self, key: str, local_id: str, body: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/v1/projects/{key}/items/{local_id}/ship", json=body,
        )

    async def create_item_event(
        self, key: str, local_id: str, body: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/v1/projects/{key}/items/{local_id}/events", json=body,
        )

    async def delete_item(self, key: str, local_id: str) -> dict[str, Any]:
        return await self._request(
            "DELETE", f"/api/v1/projects/{key}/items/{local_id}",
        )

    async def get_item(self, key: str, local_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/api/v1/projects/{key}/items/{local_id}",
        )

    async def list_items(
        self, key: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "GET", f"/api/v1/projects/{key}/items", params=params,
        )

    async def search_items(
        self, key: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "GET", f"/api/v1/projects/{key}/search", params=params,
        )

    async def add_relationship(
        self, key: str, from_local_id: str, body: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/projects/{key}/items/{from_local_id}/relationships",
            json=body,
        )

    async def remove_relationship(
        self, key: str, rel_id: int,
    ) -> dict[str, Any]:
        return await self._request(
            "DELETE", f"/api/v1/projects/{key}/relationships/{rel_id}",
        )

    async def start_work_session(
        self, key: str, body: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/v1/projects/{key}/work-sessions", json=body,
        )

    async def list_work_sessions(
        self, key: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "GET", f"/api/v1/projects/{key}/work-sessions", params=params,
        )

    async def get_work_session(
        self, key: str, session_id: int,
    ) -> dict[str, Any]:
        return await self._request(
            "GET", f"/api/v1/projects/{key}/work-sessions/{session_id}",
        )

    async def update_work_session(
        self, key: str, session_id: int, body: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/projects/{key}/work-sessions/{session_id}/updates",
            json=body,
        )

    async def finish_work_session(
        self, key: str, session_id: int, body: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/projects/{key}/work-sessions/{session_id}/finish",
            json=body,
        )


_client: IssueDeckClient | None = None


def get_client() -> IssueDeckClient:
    """Return a process-wide singleton built from ISSUEDECK_* env vars."""
    global _client
    if _client is None:
        base = os.environ.get("ISSUEDECK_BASE_URL", "http://127.0.0.1:8765")
        token = os.environ.get("ISSUEDECK_TOKEN", "")
        if not token:
            raise RuntimeError("ISSUEDECK_TOKEN env var is required")
        _client = IssueDeckClient(base_url=base, token=token)
    return _client
