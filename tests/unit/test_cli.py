import subprocess
import sys

import pytest

from issuedeck.cli import _build_registry
from issuedeck.core.errors import ConfigError


def test_issuedeck_help_lists_subcommands():
    r = subprocess.run(
        [sys.executable, "-m", "issuedeck", "--help"],
        capture_output=True, text=True,
    )
    out = r.stdout + r.stderr
    for cmd in ("serve", "migrate", "export", "seed-demo", "mcp"):
        assert cmd in out, f"{cmd} missing from --help"


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
