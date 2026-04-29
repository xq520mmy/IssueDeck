import pytest
from pydantic import ValidationError

from issuedeck.features.items.schemas import (
    CreateItemEventRequest,
    CreateItemRequest,
    ItemDetail,
    ItemSummary,
    ShipItemRequest,
    UpdateItemRequest,
)


def test_create_item_request_minimal():
    r = CreateItemRequest(kind="feature", title="Hello")
    assert r.kind == "feature"
    assert r.body == ""
    assert r.tags == []
    assert r.applies_to is None


def test_create_item_request_empty_title_rejected():
    with pytest.raises(ValidationError):
        CreateItemRequest(kind="feature", title="")


def test_update_item_request_body_vs_append_mutex():
    with pytest.raises(ValidationError):
        UpdateItemRequest(body="x", append_body="y")


def test_update_item_request_status_done_rejected():
    with pytest.raises(ValidationError):
        UpdateItemRequest(status="done")


def test_ship_item_request_requires_version():
    with pytest.raises(ValidationError):
        ShipItemRequest(branch="v3", version="")


def test_create_item_event_request_defaults_to_comment():
    r = CreateItemEventRequest(body="Leaving a handoff note.")
    assert r.event_type == "comment"
    assert r.actor_type == "human"
    assert r.metadata == {}


def test_create_item_event_request_rejects_empty_body():
    with pytest.raises(ValidationError):
        CreateItemEventRequest(body="")


def test_item_summary_roundtrip():
    data = {
        "project_key": "p", "local_id": "FEAT-0001", "kind": "feature",
        "status": "proposed", "title": "Hello", "body_preview": "hi",
        "tags": ["a"], "applies_to": ["v3"],
        "created_at": "t", "updated_at": "t", "deleted_at": None,
    }
    s = ItemSummary(**data)
    assert s.model_dump()["local_id"] == "FEAT-0001"


def test_item_detail_has_body_and_ship_records():
    data = {
        "project_key": "p", "local_id": "FEAT-0001", "kind": "feature",
        "status": "done", "title": "Hello", "body": "full body",
        "tags": [], "applies_to": ["v3"],
        "created_at": "t", "updated_at": "t", "deleted_at": None,
        "ship_records": [
            {"branch_key": "v3", "version": "0.4.2",
             "shipped_at": "t", "commits": ["abc"]}
        ],
        "relationships": [],
    }
    d = ItemDetail(**data)
    assert d.ship_records[0].version == "0.4.2"
