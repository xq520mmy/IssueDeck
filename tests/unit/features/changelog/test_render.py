from issuedeck.features.changelog.render import render_changelog_markdown


def test_renders_sections_by_version():
    rows = [
        {"local_id": "FEAT-0001", "kind": "feature", "title": "A thing",
         "version": "0.2.0", "shipped_at": "2026-04-10T00:00:00+00:00",
         "commits": ["abc1234"]},
        {"local_id": "BUG-0003", "kind": "bug", "title": "B thing",
         "version": "0.2.0", "shipped_at": "2026-04-10T00:00:00+00:00",
         "commits": []},
        {"local_id": "FEAT-0002", "kind": "feature", "title": "C thing",
         "version": "0.1.0", "shipped_at": "2026-03-15T00:00:00+00:00",
         "commits": ["def5678"]},
    ]
    md = render_changelog_markdown(project_name="Test", branch_label="v3", rows=rows)
    assert "# Test — v3 Changelog" in md
    assert "## 0.2.0" in md
    assert "## 0.1.0" in md
    assert md.index("## 0.2.0") < md.index("## 0.1.0")
    assert "### Features" in md
    assert "### Bugs" in md
    assert "FEAT-0001" in md
    assert "abc1234" in md


def test_empty_rows_returns_header_only():
    md = render_changelog_markdown(project_name="Test", branch_label="v3", rows=[])
    assert "# Test — v3 Changelog" in md
    assert "_no shipped items yet_" in md
