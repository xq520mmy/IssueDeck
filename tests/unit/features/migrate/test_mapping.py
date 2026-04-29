from pathlib import Path

import frontmatter

from issuedeck.features.migrate.frontmatter import map_frontmatter_to_row

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
