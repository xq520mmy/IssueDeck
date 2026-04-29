import httpx
import pytest

from issuedeck.core.errors import (
    InvalidKind,
    IssueDeckError,
    ItemNotFound,
    RelationshipDuplicate,
)
from issuedeck.mcp.client import IssueDeckClient, _raise_for_error


def _resp(status: int, code: str, message: str = "boom") -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json={"error": {"code": code, "message": message}},
        request=httpx.Request("GET", "http://x/"),
    )


def test_raise_for_error_maps_item_not_found():
    with pytest.raises(ItemNotFound) as exc:
        _raise_for_error(_resp(404, "item_not_found", "missing"))
    assert "missing" in str(exc.value)


def test_raise_for_error_maps_invalid_kind():
    with pytest.raises(InvalidKind):
        _raise_for_error(_resp(422, "invalid_kind"))


def test_raise_for_error_maps_relationship_duplicate():
    with pytest.raises(RelationshipDuplicate):
        _raise_for_error(_resp(409, "relationship_duplicate"))


def test_raise_for_error_unknown_code_falls_back_to_issuedeck_error():
    with pytest.raises(IssueDeckError):
        _raise_for_error(_resp(500, "internal_error"))


def test_raise_for_error_passes_through_2xx():
    r = httpx.Response(200, json={"ok": True},
                        request=httpx.Request("GET", "http://x/"))
    _raise_for_error(r)  # must not raise


async def test_client_injects_bearer_token(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"projects": []})

    transport = httpx.MockTransport(handler)
    client = IssueDeckClient(
        base_url="http://issuedeck.local",
        token="secret-token-value",
        transport=transport,
    )
    await client.list_projects()
    await client.aclose()
    assert captured["auth"] == "Bearer secret-token-value"


async def test_client_list_projects_returns_parsed_payload():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/projects"
        return httpx.Response(200, json={"projects": [{"key": "demo"}]})

    client = IssueDeckClient(
        base_url="http://issuedeck.local",
        token="t",
        transport=httpx.MockTransport(handler),
    )
    data = await client.list_projects()
    await client.aclose()
    assert data == {"projects": [{"key": "demo"}]}


async def test_client_add_relationship_uses_item_scoped_route():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["json"] = request.content.decode()
        return httpx.Response(
            201,
            json={
                "rel_id": 7,
                "from_local_id": "FEAT-1",
                "to_local_id": "BUG-2",
                "relation_type": "blocks",
            },
        )

    client = IssueDeckClient(
        base_url="http://issuedeck.local",
        token="t",
        transport=httpx.MockTransport(handler),
    )
    data = await client.add_relationship(
        "demo",
        "FEAT-1",
        {"to_local_id": "BUG-2", "relation_type": "blocks"},
    )
    await client.aclose()

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/projects/demo/items/FEAT-1/relationships"
    assert captured["json"] == '{"to_local_id":"BUG-2","relation_type":"blocks"}'
    assert data["rel_id"] == 7


async def test_client_create_item_event_uses_item_events_route():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["json"] = request.content.decode()
        return httpx.Response(
            201,
            json={
                "id": 1,
                "event_type": "comment",
                "actor_type": "agent",
                "actor_name": "codex",
                "body": "Verified.",
                "metadata": {},
                "created_at": "t",
            },
        )

    client = IssueDeckClient(
        base_url="http://issuedeck.local",
        token="t",
        transport=httpx.MockTransport(handler),
    )
    data = await client.create_item_event(
        "demo",
        "FEAT-1",
        {"event_type": "comment", "actor_type": "agent",
         "actor_name": "codex", "body": "Verified."},
    )
    await client.aclose()

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/projects/demo/items/FEAT-1/events"
    assert '"body":"Verified."' in captured["json"]
    assert data["id"] == 1
