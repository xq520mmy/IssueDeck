
from issuedeck.core.errors import (
    ConfigError,
    InvalidKind,
    IssueDeckError,
    ItemNotFound,
    ProjectNotFound,
    RelationshipDuplicate,
    RelationshipSelfLoop,
    Unauthorized,
)


def test_all_errors_inherit_issuedeck_error():
    for cls in [
        ConfigError, ProjectNotFound, ItemNotFound,
        InvalidKind, RelationshipSelfLoop, RelationshipDuplicate, Unauthorized,
    ]:
        assert issubclass(cls, IssueDeckError)


def test_code_unique_per_class():
    codes = {
        ConfigError.code, ProjectNotFound.code, ItemNotFound.code,
        InvalidKind.code, RelationshipSelfLoop.code,
        RelationshipDuplicate.code, Unauthorized.code,
    }
    assert len(codes) == 7


def test_http_status_is_classvar():
    assert ProjectNotFound.http_status == 404
    assert ItemNotFound.http_status == 404
    assert InvalidKind.http_status == 422
    assert RelationshipSelfLoop.http_status == 409
    assert Unauthorized.http_status == 401


def test_details_defaults_to_empty_dict():
    e = ItemNotFound("item FEAT-0001 not found")
    assert e.details == {}
    assert e.message == "item FEAT-0001 not found"


def test_details_are_preserved():
    e = ItemNotFound("x", details={"project_key": "sample", "local_id": "FEAT-0001"})
    assert e.details == {"project_key": "sample", "local_id": "FEAT-0001"}


def test_str_format():
    e = InvalidKind("kind 'spike' unknown")
    assert "kind 'spike' unknown" in str(e)
