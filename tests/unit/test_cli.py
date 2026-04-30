import asyncio
import sqlite3
import subprocess
import sys

import pytest

from issuedeck.cli import (
    _build_registry,
    _cmd_demo,
    _cmd_import_github_url,
    _ensure_demo_config,
    _ensure_demo_project_config,
)
from issuedeck.core.config import load_server_config
from issuedeck.core.errors import ConfigError


def test_issuedeck_help_lists_subcommands():
    r = subprocess.run(
        [sys.executable, "-m", "issuedeck", "--help"],
        capture_output=True, text=True,
    )
    out = r.stdout + r.stderr
    for cmd in (
        "demo",
        "serve",
        "migrate",
        "export",
        "seed-demo",
        "import-github-url",
        "mcp",
    ):
        assert cmd in out, f"{cmd} missing from --help"


def test_migrate_help_lists_presets():
    r = subprocess.run(
        [sys.executable, "-m", "issuedeck", "migrate", "--help"],
        capture_output=True, text=True,
    )
    out = r.stdout + r.stderr
    assert "--preset" in out
    assert "github" in out
    assert "linear" in out


def test_ensure_demo_config_writes_missing_config(tmp_path):
    cfg_path = tmp_path / "server.toml"

    assert _ensure_demo_config(cfg_path) is True
    text = cfg_path.read_text(encoding="utf-8")
    assert 'api_token = "issuedeck-local-token"' in text
    assert 'data_dir = "' in text
    assert 'projects_dir = "' in text

    original = text.replace("issuedeck-local-token", "custom-token")
    cfg_path.write_text(original, encoding="utf-8")
    assert _ensure_demo_config(cfg_path) is False
    assert cfg_path.read_text(encoding="utf-8") == original


def test_demo_prepare_creates_config_project_db_and_fake_data(tmp_path, monkeypatch):
    monkeypatch.delenv("ISSUEDECK_API_TOKEN", raising=False)
    monkeypatch.delenv("ISSUEDECK_DATA_DIR", raising=False)
    monkeypatch.delenv("ISSUEDECK_PROJECTS_DIR", raising=False)

    cfg_path = tmp_path / "server.toml"

    rc = _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )

    assert rc == 0
    assert cfg_path.exists()
    assert (tmp_path / "projects" / "example.toml").exists()
    assert (tmp_path / "data" / "tracker.db").exists()
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        item_count = conn.execute(
            "select count(*) from items where project_key = 'example'"
        ).fetchone()[0]
    assert item_count == 8


def test_import_github_url_dry_run_prints_create_payload(tmp_path, capsys):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )

    rc = asyncio.run(_cmd_import_github_url(
        cfg_path,
        "example",
        "https://github.com/example/repo/issues/42",
        kind="bug",
        title=None,
        body=None,
        tags=[],
        applies_to=None,
        link_label=None,
        dry_run=True,
    ))

    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "bug"' in out
    assert '"title": "Review GitHub issue #42 from example/repo"' in out
    assert '"link_type": "github_issue"' in out


def test_import_github_url_creates_linked_item(tmp_path):
    cfg_path = tmp_path / "server.toml"
    _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )

    rc = asyncio.run(_cmd_import_github_url(
        cfg_path,
        "example",
        "https://github.com/example/repo/pull/7",
        kind="feature",
        title="Track upstream PR",
        body=None,
        tags=["upstream"],
        applies_to=["main"],
        link_label=None,
        dry_run=False,
    ))

    assert rc == 0
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        row = conn.execute(
            """
            select items.title, item_external_links.link_type, item_external_links.url
            from items
            join item_external_links on item_external_links.item_pk = items.pk
            where items.title = 'Track upstream PR'
            """
        ).fetchone()
    assert row == (
        "Track upstream PR",
        "github_pr",
        "https://github.com/example/repo/pull/7",
    )

    rc = _cmd_demo(
        cfg_path,
        "example",
        host=None,
        port=None,
        force_reset_demo_data=False,
        open_browser=False,
        serve=False,
    )
    assert rc == 0
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        item_count = conn.execute(
            "select count(*) from items where project_key = 'example'"
        ).fetchone()[0]
    assert item_count == 9


def test_import_github_url_runs_migrations_for_empty_database(tmp_path):
    cfg_path = tmp_path / "server.toml"
    _ensure_demo_config(cfg_path)
    server_cfg = load_server_config(cfg_path)
    _ensure_demo_project_config(server_cfg.projects_dir, "example")

    rc = asyncio.run(_cmd_import_github_url(
        cfg_path,
        "example",
        "https://github.com/example/repo/issues/42",
        kind="bug",
        title=None,
        body=None,
        tags=[],
        applies_to=None,
        link_label=None,
        dry_run=False,
    ))

    assert rc == 0
    with sqlite3.connect(tmp_path / "data" / "tracker.db") as conn:
        row = conn.execute(
            """
            select items.title, item_external_links.link_type
            from items
            join item_external_links on item_external_links.item_pk = items.pk
            where items.local_id = 'BUG-0001'
            """
        ).fetchone()
    assert row == (
        "Review GitHub issue #42 from example/repo",
        "github_issue",
    )


def test_cli_registry_rejects_project_key_filename_mismatch(tmp_path):
    projects_dir = tmp_path / "projects"
    data_dir = tmp_path / "data"
    projects_dir.mkdir()
    data_dir.mkdir()
    (tmp_path / "server.toml").write_text(
        "\n".join([
            'api_token = "token"',
            f'projects_dir = "{projects_dir.as_posix()}"',
            f'data_dir = "{data_dir.as_posix()}"',
        ]),
        encoding="utf-8",
    )
    (projects_dir / "demo.toml").write_text(
        "\n".join([
            'key = "other"',
            'name = "Other"',
            "[kinds.feature]",
            'label = "Feature"',
            'prefix = "FEAT"',
            "[statuses.proposed]",
            'label = "Proposed"',
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="filename stem"):
        _build_registry(tmp_path / "server.toml")
