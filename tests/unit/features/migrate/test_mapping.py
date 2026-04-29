from pathlib import Path

import frontmatter

from issuedeck.features.migrate.frontmatter import FrontmatterMapping, map_frontmatter_to_row

FIX = Path(__file__).parent.parent.parent.parent / "integration/features/migrate/fixtures"


def test_map_full_row():
    fm = frontmatter.load(FIX / "items/FEAT-0001.md")
    row = map_frontmatter_to_row(fm, is_archived=False)
    assert row.local_id == "FEAT-0001"
    assert row.kind == "feature"
    assert row.status == "done"
    assert row.tags == ["core", "performance"]
    assert row.applies_to == ["v3", "v2"]
    assert len(row.ship_records) == 1
    assert row.ship_records[0].branch_key == "v3"
    assert row.ship_records[0].version == "0.4.2"
    assert row.ship_records[0].commits == ["abc123", "def456"]
    assert row.deleted_at is None
    assert "Full body text" in row.body


def test_map_minimal_row_no_ship():
    fm = frontmatter.load(FIX / "items/FEAT-0002.md")
    row = map_frontmatter_to_row(fm, is_archived=False)
    assert row.ship_records == []
    assert row.tags == []
    assert row.applies_to == ["v3"]


def test_map_common_alias_fields():
    fm = frontmatter.loads("""---
id: BUG-0010
type: bug
state: proposed
title: Alias import
labels: [migration, bug]
applies_to: v3
---
Body
""")

    row = map_frontmatter_to_row(fm, is_archived=False)

    assert row.local_id == "BUG-0010"
    assert row.kind == "bug"
    assert row.status == "proposed"
    assert row.tags == ["migration", "bug"]
    assert row.applies_to == ["v3"]


def test_map_custom_alias_fields():
    mapping = FrontmatterMapping.from_alias_options([
        "kind=category",
        "status=workflow",
        "tags=keywords",
        "applies_to=branches",
    ])
    fm = frontmatter.loads("""---
id: FEAT-0010
category: feature
workflow: done
title: Custom import
keywords: migration, release
branches: [v3, v2]
---
Body
""")

    row = map_frontmatter_to_row(fm, is_archived=False, mapping=mapping)

    assert row.kind == "feature"
    assert row.status == "done"
    assert row.tags == ["migration", "release"]
    assert row.applies_to == ["v3", "v2"]


def test_github_preset_maps_export_url():
    mapping = FrontmatterMapping.from_alias_options([], presets=["github"])
    fm = frontmatter.loads("""---
id: BUG-0011
type: bug
state: proposed
title: GitHub export
labels: [migration]
html_url: https://github.com/example/repo/issues/11?from=export
---
Body
""")

    row = map_frontmatter_to_row(fm, is_archived=False, mapping=mapping)

    assert row.external_links == [{
        "link_type": "github_issue",
        "label": "Issue #11",
        "url": "https://github.com/example/repo/issues/11",
    }]


def test_linear_preset_maps_identifier_and_links():
    mapping = FrontmatterMapping.from_alias_options([], presets=["linear"])
    fm = frontmatter.loads("""---
identifier: FEAT-0012
type: feature
workflow_state: done
title: Linear export
label_names: [migration, ux]
branch: v3
links:
  - https://github.com/example/repo/pull/12
---
Body
""")

    row = map_frontmatter_to_row(fm, is_archived=False, mapping=mapping)

    assert row.local_id == "FEAT-0012"
    assert row.status == "done"
    assert row.tags == ["migration", "ux"]
    assert row.applies_to == ["v3"]
    assert row.external_links[0]["link_type"] == "github_pr"


def test_unknown_alias_field_fails_fast():
    try:
        FrontmatterMapping.from_alias_options(["unknown=legacy"])
    except ValueError as exc:
        assert "unknown frontmatter field" in str(exc)
    else:
        raise AssertionError("expected invalid alias mapping to fail")


def test_unknown_preset_fails_fast():
    try:
        FrontmatterMapping.from_alias_options([], presets=["unknown"])
    except ValueError as exc:
        assert "unknown frontmatter preset" in str(exc)
    else:
        raise AssertionError("expected invalid preset to fail")
