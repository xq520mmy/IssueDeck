import sqlite3
import subprocess
import sys

import pytest

from issuedeck.cli import _build_registry, _cmd_demo, _ensure_demo_config
from issuedeck.core.errors import ConfigError


def test_issuedeck_help_lists_subcommands():
    r = subprocess.run(
        [sys.executable, "-m", "issuedeck", "--help"],
        capture_output=True, text=True,
    )
    out = r.stdout + r.stderr
    for cmd in ("demo", "serve", "migrate", "export", "seed-demo", "mcp"):
        assert cmd in out, f"{cmd} missing from --help"


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
    assert item_count == 8


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
