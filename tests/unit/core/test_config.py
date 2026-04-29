from pathlib import Path

import pytest
from pydantic import ValidationError

from issuedeck.core.config import (
    ConfigRegistry,
    ServerConfig,
    load_project_config,
    load_server_config,
)
from issuedeck.core.errors import ProjectNotFound

FIX = Path(__file__).parent / "fixtures"


def test_load_server_config_ok():
    cfg = load_server_config(FIX / "server_ok.toml")
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8765
    assert cfg.api_token.get_secret_value() == "secret-token-xyz"


def test_load_server_config_accepts_utf8_bom(tmp_path):
    cfg_path = tmp_path / "server.toml"
    cfg_path.write_text(
        'host = "127.0.0.1"\nport = 8765\napi_token = "secret-token-xyz"\n',
        encoding="utf-8-sig",
    )
    cfg = load_server_config(cfg_path)
    assert cfg.host == "127.0.0.1"
    assert cfg.api_token.get_secret_value() == "secret-token-xyz"


def test_server_env_override(monkeypatch):
    monkeypatch.setenv("ISSUEDECK_API_TOKEN", "env-token")
    monkeypatch.setenv("ISSUEDECK_PORT", "9000")
    cfg = load_server_config(FIX / "server_ok.toml")
    assert cfg.api_token.get_secret_value() == "env-token"
    assert cfg.port == 9000


def test_load_project_config_ok():
    pc = load_project_config(FIX / "project_ok.toml")
    assert pc.key == "sample"
    assert set(pc.kinds.keys()) == {"feature", "bug"}
    assert pc.kinds["feature"].prefix == "FEAT"
    assert {b.key for b in pc.branches} == {"v2", "v3"}


def test_project_config_rejects_lowercase_prefix():
    with pytest.raises(ValidationError):
        load_project_config(FIX / "project_bad_prefix.toml")


def test_project_config_requires_ship_but_no_branches(tmp_path):
    p = tmp_path / "p.toml"
    p.write_text(
        'key="p"\nname="P"\n'
        '[kinds.feature]\nlabel="Feature"\nprefix="FEAT"\n'
        '[statuses.done]\nlabel="Done"\nrequires_ship=true\n'
    )
    with pytest.raises(ValidationError):
        load_project_config(p)


def test_registry_project_not_found():
    registry = ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={},
    )
    with pytest.raises(ProjectNotFound):
        registry.project("unknown")


def test_registry_validate_kind():
    pc = load_project_config(FIX / "project_ok.toml")
    registry = ConfigRegistry(
        server=ServerConfig(api_token="t"),
        projects={"sample": pc},
    )
    kc = registry.validate_kind("sample", "feature")
    assert kc.prefix == "FEAT"

    from issuedeck.core.errors import InvalidKind
    with pytest.raises(InvalidKind):
        registry.validate_kind("sample", "spike")
