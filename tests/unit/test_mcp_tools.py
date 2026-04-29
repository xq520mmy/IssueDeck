import pytest

from issuedeck.mcp import tools


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    async def _record(self, name: str, *args, **kwargs) -> dict:
        self.calls.append((name, args, kwargs))
        return {"ok": True, "name": name}

    async def list_projects(self):
        return await self._record("list_projects")

    async def get_project_config(self, key):
        return await self._record("get_project_config", key)

    async def create_item(self, key, body):
        return await self._record("create_item", key, body=body)

    async def update_item(self, key, local_id, body):
        return await self._record("update_item", key, local_id, body=body)

    async def ship_item(self, key, local_id, body):
        return await self._record("ship_item", key, local_id, body=body)

    async def create_item_event(self, key, local_id, body):
        return await self._record("create_item_event", key, local_id, body=body)

    async def delete_item(self, key, local_id):
        return await self._record("delete_item", key, local_id)

    async def get_item(self, key, local_id):
        return await self._record("get_item", key, local_id)

    async def list_items(self, key, params):
        return await self._record("list_items", key, params=params)

    async def search_items(self, key, params):
        return await self._record("search_items", key, params=params)

    async def add_relationship(self, key, from_local_id, body):
        return await self._record(
            "add_relationship", key, from_local_id, body=body,
        )

    async def remove_relationship(self, key, rel_id):
        return await self._record("remove_relationship", key, rel_id)


@pytest.fixture
def fake_client(monkeypatch):
    fc = _FakeClient()
    monkeypatch.setattr(tools, "get_client", lambda: fc)
    return fc


async def test_list_projects(fake_client):
    result = await tools.list_projects()
    assert result == {"ok": True, "name": "list_projects"}
    assert fake_client.calls == [("list_projects", (), {})]


async def test_create_item_builds_body(fake_client):
    await tools.create_item(
        project_key="demo", kind="feature", title="Add search",
        body="", tags=["ui"], applies_to=["web"],
    )
    name, args, kwargs = fake_client.calls[0]
    assert name == "create_item"
    assert args == ("demo",)
    assert kwargs["body"] == {
        "kind": "feature",
        "title": "Add search",
        "body": "",
        "tags": ["ui"],
        "applies_to": ["web"],
    }


async def test_update_item_omits_unset(fake_client):
    await tools.update_item(
        project_key="demo", local_id="FEAT-1",
        title="Renamed", append_body=None, status=None, tags=None,
        applies_to=None, body=None,
    )
    _, _, kwargs = fake_client.calls[0]
    assert kwargs["body"] == {"title": "Renamed"}


async def test_ship_item_passes_commits(fake_client):
    await tools.ship_item(
        project_key="demo", local_id="FEAT-1",
        branch="main", version="v0.2.0", commits=["abc123"],
    )
    _, args, kwargs = fake_client.calls[0]
    assert args == ("demo", "FEAT-1")
    assert kwargs["body"] == {
        "branch": "main",
        "version": "v0.2.0",
        "commits": ["abc123"],
    }


async def test_append_item_event_builds_body(fake_client):
    await tools.append_item_event(
        project_key="demo",
        local_id="FEAT-1",
        body="Verified the dashboard flow.",
        event_type="comment",
        actor_type="agent",
        actor_name="codex",
        metadata={"url": "/dashboard/demo/items/FEAT-1"},
    )
    _, args, kwargs = fake_client.calls[0]
    assert args == ("demo", "FEAT-1")
    assert kwargs["body"] == {
        "event_type": "comment",
        "actor_type": "agent",
        "actor_name": "codex",
        "body": "Verified the dashboard flow.",
        "metadata": {"url": "/dashboard/demo/items/FEAT-1"},
    }


async def test_list_items_builds_params(fake_client):
    await tools.list_items(
        project_key="demo", status="active", kind="feature",
        tag=["ui", "p1"], applies_to="web", relation_type="blocked_by",
        shipped_in_branch=None, since=None, include_deleted=False,
        only_deleted=True, after=None, limit=20,
    )
    _, _, kwargs = fake_client.calls[0]
    params = kwargs["params"]
    assert params["status"] == "active"
    assert params["kind"] == "feature"
    assert params["tag"] == ["ui", "p1"]
    assert params["applies_to"] == "web"
    assert params["relation_type"] == "blocked_by"
    assert params["limit"] == 20
    assert params["only_deleted"] == "true"
    assert "shipped_in_branch" not in params
    assert "since" not in params
    assert "after" not in params


async def test_search_items_forwards_query(fake_client):
    await tools.search_items(project_key="demo", q="auth*", limit=15)
    _, args, kwargs = fake_client.calls[0]
    assert args == ("demo",)
    assert kwargs["params"] == {"q": "auth*", "limit": 15}


async def test_relationship_tools(fake_client):
    await tools.add_relationship(
        project_key="demo", from_local_id="FEAT-1",
        to_local_id="BUG-2", relation_type="blocks",
    )
    await tools.remove_relationship(project_key="demo", rel_id=42)
    names = [c[0] for c in fake_client.calls]
    assert names == ["add_relationship", "remove_relationship"]
    assert fake_client.calls[0][1] == ("demo", "FEAT-1")
    assert fake_client.calls[0][2]["body"] == {
        "to_local_id": "BUG-2",
        "relation_type": "blocks",
    }
    assert fake_client.calls[1][1] == ("demo", 42)
