#!/usr/bin/env python3
"""Smoke-test an IssueDeck SQLite backup before a real restore."""

from __future__ import annotations

import argparse
import gzip
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REQUIRED_TABLES = {
    "items",
    "item_tags",
    "item_applies_to",
    "ship_records",
    "ship_commits",
    "item_relationships",
    "item_events",
    "item_external_links",
    "alembic_version",
}


def restore_backup(source: Path, out: Path) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"backup not found: {source}")

    out.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix == ".gz":
        with gzip.open(source, "rb") as src, out.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    else:
        shutil.copy2(source, out)
    return out


def smoke_check(db_path: Path) -> tuple[int, int]:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"integrity_check failed: {integrity}")

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            raise RuntimeError("missing required tables: " + ", ".join(missing))

        items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        projects = conn.execute("SELECT COUNT(DISTINCT project_key) FROM items").fetchone()[0]
        return items, projects
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Restore an IssueDeck backup to a scratch DB and validate it.",
    )
    parser.add_argument("backup", help="Path to tracker-*.db or tracker-*.db.gz")
    parser.add_argument(
        "--out",
        help="Optional restored DB path. Defaults to a temporary scratch file.",
    )
    args = parser.parse_args(argv)

    backup = Path(args.backup)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(args.out) if args.out else Path(tmp) / "issuedeck-restore-smoke.db"
        try:
            restored = restore_backup(backup, out)
            items, projects = smoke_check(restored)
        except Exception as exc:
            print(f"[fail] restore smoke failed: {exc}", file=sys.stderr)
            return 1

        print(f"[ok] restored={restored}")
        print("[ok] integrity_check=ok")
        print(f"[ok] items={items} projects={projects}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
