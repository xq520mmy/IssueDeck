import json

from issuedeck.features.dashboard.saved_filters import (
    delete_dashboard_filter,
    filter_params_from_form,
    list_saved_dashboard_filters,
    save_dashboard_filter,
)


def test_saved_filters_are_project_scoped(tmp_path):
    save_dashboard_filter(
        tmp_path,
        "alpha",
        "Active bugs",
        {"view": "active", "kind": ["bug"], "include_deleted": False},
    )
    save_dashboard_filter(
        tmp_path,
        "beta",
        "Ready work",
        {"view": "ready_to_ship"},
    )

    alpha = list_saved_dashboard_filters(tmp_path, "alpha")
    beta = list_saved_dashboard_filters(tmp_path, "beta")

    assert [item.name for item in alpha] == ["Active bugs"]
    assert alpha[0].params == {"view": "active", "kind": ["bug"]}
    assert [item.name for item in beta] == ["Ready work"]


def test_saved_filter_ids_are_unique(tmp_path):
    first = save_dashboard_filter(tmp_path, "alpha", "Active bugs", {"view": "active"})
    second = save_dashboard_filter(tmp_path, "alpha", "Active bugs", {"view": "recent"})

    assert first.id == "active-bugs"
    assert second.id == "active-bugs-2"
    assert [item.id for item in list_saved_dashboard_filters(tmp_path, "alpha")] == [
        "active-bugs-2",
        "active-bugs",
    ]


def test_saved_filter_delete_removes_only_matching_project(tmp_path):
    alpha = save_dashboard_filter(tmp_path, "alpha", "Active bugs", {"view": "active"})
    save_dashboard_filter(tmp_path, "alpha", "Ready work", {"view": "ready_to_ship"})
    beta = save_dashboard_filter(tmp_path, "beta", "Active bugs", {"view": "active"})

    assert delete_dashboard_filter(tmp_path, "alpha", alpha.id) is True
    assert delete_dashboard_filter(tmp_path, "alpha", "missing") is False

    assert [item.name for item in list_saved_dashboard_filters(tmp_path, "alpha")] == [
        "Ready work",
    ]
    assert [item.id for item in list_saved_dashboard_filters(tmp_path, "beta")] == [
        beta.id,
    ]


def test_filter_params_from_form_normalizes_values():
    params = filter_params_from_form(
        view="recent",
        kind=["feature", "feature", ""],
        status=["proposed"],
        tag=None,
        applies_to=["main"],
        relation_type=[],
        include_deleted=True,
    )

    assert params == {
        "view": "recent",
        "kind": ["feature"],
        "status": ["proposed"],
        "applies_to": ["main"],
        "include_deleted": True,
    }


def test_corrupt_store_falls_back_to_empty_list(tmp_path):
    (tmp_path / "dashboard_filters.json").write_text("{bad json", encoding="utf-8")

    assert list_saved_dashboard_filters(tmp_path, "alpha") == []


def test_store_uses_local_json_file(tmp_path):
    save_dashboard_filter(tmp_path, "alpha", "Feature work", {"kind": ["feature"]})

    raw = json.loads((tmp_path / "dashboard_filters.json").read_text(encoding="utf-8"))
    assert raw["projects"]["alpha"][0]["name"] == "Feature work"
