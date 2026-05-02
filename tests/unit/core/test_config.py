from pathlib import Path

import pytest
from pydantic import ValidationError

from issuedeck.core.config import (
    ConfigRegistry,
    EmailNotificationConfig,
    NotificationConfig,
    ServerConfig,
    WebhookConfig,
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
    monkeypatch.setenv("ISSUEDECK_PROJECT_TEMPLATES_DIR", "./custom-templates")
    cfg = load_server_config(FIX / "server_ok.toml")
    assert cfg.api_token.get_secret_value() == "env-token"
    assert cfg.port == 9000
    assert cfg.project_templates_dir == Path("./custom-templates")


def test_server_config_supports_scoped_tokens(tmp_path):
    cfg_path = tmp_path / "server.toml"
    cfg_path.write_text(
        "\n".join([
            'api_token = "legacy-admin"',
            "",
            "[[tokens]]",
            'name = "readonly"',
            'token = "read-token"',
            'scopes = ["read-only"]',
            "",
            "[[tokens]]",
            'name = "agent"',
            'token = "agent-token"',
            'scopes = ["agent"]',
            "",
        ]),
        encoding="utf-8",
    )

    cfg = load_server_config(cfg_path)
    tokens = {token.name: token for token in cfg.auth_tokens()}
    assert tokens["api_token"].normalized_scopes() == {"admin"}
    assert tokens["readonly"].normalized_scopes() == {"read"}
    assert tokens["agent"].normalized_scopes() == {"agent"}


def test_server_config_rejects_duplicate_token_values(tmp_path):
    cfg_path = tmp_path / "server.toml"
    cfg_path.write_text(
        "\n".join([
            'api_token = "same-token"',
            "",
            "[[tokens]]",
            'name = "agent"',
            'token = "same-token"',
            'scopes = ["agent"]',
            "",
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="duplicate token value"):
        load_server_config(cfg_path)


def test_server_config_supports_lifecycle_webhooks(tmp_path):
    cfg_path = tmp_path / "server.toml"
    cfg_path.write_text(
        "\n".join([
            'api_token = "legacy-admin"',
            "",
            "[[webhooks]]",
            'name = "automation"',
            'url = "https://example.com/hooks/issuedeck"',
            'secret = "shared-secret"',
            'events = ["item.created", "item.shipped"]',
            "retries = 2",
            "timeout_seconds = 3",
            "backoff_seconds = 0.1",
            "",
        ]),
        encoding="utf-8",
    )

    cfg = load_server_config(cfg_path)

    assert cfg.webhooks[0].name == "automation"
    assert cfg.webhooks[0].events == ["item.created", "item.shipped"]
    assert cfg.webhooks[0].secret.get_secret_value() == "shared-secret"


def test_server_config_rejects_duplicate_webhook_names():
    with pytest.raises(ValidationError, match="duplicate webhook name"):
        ServerConfig(
            api_token="legacy-admin",
            webhooks=[
                WebhookConfig(
                    name="automation",
                    url="https://example.com/one",
                    secret="one",
                ),
                WebhookConfig(
                    name="automation",
                    url="https://example.com/two",
                    secret="two",
                ),
            ],
        )


def test_server_config_supports_lifecycle_notifications(tmp_path):
    cfg_path = tmp_path / "server.toml"
    cfg_path.write_text(
        "\n".join([
            'api_token = "legacy-admin"',
            "",
            "[[notifications]]",
            'name = "team-alerts"',
            'provider = "slack"',
            'url = "https://hooks.slack.com/services/T000/B000/secret"',
            'events = ["item.created", "item.shipped"]',
            "retries = 2",
            "timeout_seconds = 3",
            "backoff_seconds = 0.1",
            "",
            "[[notifications]]",
            'name = "release-room"',
            'provider = "discord"',
            'url = "https://discord.com/api/webhooks/123/secret"',
            'events = ["item.shipped"]',
            "",
        ]),
        encoding="utf-8",
    )

    cfg = load_server_config(cfg_path)

    assert cfg.notifications[0].name == "team-alerts"
    assert cfg.notifications[0].provider == "slack"
    assert cfg.notifications[0].events == ["item.created", "item.shipped"]
    assert cfg.notifications[0].url.get_secret_value().startswith("https://hooks.")
    assert cfg.notifications[1].provider == "discord"


def test_server_config_rejects_duplicate_notification_names():
    with pytest.raises(ValidationError, match="duplicate notification name"):
        ServerConfig(
            api_token="legacy-admin",
            notifications=[
                NotificationConfig(
                    name="team-alerts",
                    provider="slack",
                    url="https://hooks.slack.com/services/T000/B000/one",
                ),
                NotificationConfig(
                    name="team-alerts",
                    provider="discord",
                    url="https://discord.com/api/webhooks/123/two",
                ),
            ],
        )


def test_server_config_supports_email_notifications(tmp_path):
    cfg_path = tmp_path / "server.toml"
    cfg_path.write_text(
        "\n".join([
            'api_token = "legacy-admin"',
            "",
            "[[email_notifications]]",
            'name = "ops-inbox"',
            'smtp_host = "smtp.example.com"',
            "smtp_port = 587",
            'smtp_security = "starttls"',
            'username = "issuebot"',
            'password = "smtp-secret"',
            'from_email = "issuebot@example.com"',
            'to_emails = ["ops@example.com", "dev@example.com"]',
            'subject_prefix = "[IssueDeck Ops]"',
            'events = ["item.shipped"]',
            "retries = 2",
            "",
        ]),
        encoding="utf-8",
    )

    cfg = load_server_config(cfg_path)

    notification = cfg.email_notifications[0]
    assert notification.name == "ops-inbox"
    assert notification.smtp_host == "smtp.example.com"
    assert notification.to_emails == ["ops@example.com", "dev@example.com"]
    assert notification.password is not None
    assert notification.password.get_secret_value() == "smtp-secret"
    assert notification.events == ["item.shipped"]


def test_server_config_rejects_duplicate_email_notification_names():
    with pytest.raises(ValidationError, match="duplicate email notification name"):
        ServerConfig(
            api_token="legacy-admin",
            email_notifications=[
                EmailNotificationConfig(
                    name="ops-inbox",
                    smtp_host="smtp.example.com",
                    from_email="issuebot@example.com",
                    to_emails=["ops@example.com"],
                ),
                EmailNotificationConfig(
                    name="ops-inbox",
                    smtp_host="smtp.example.com",
                    from_email="issuebot@example.com",
                    to_emails=["dev@example.com"],
                ),
            ],
        )


def test_email_notification_auth_requires_username_and_password():
    with pytest.raises(ValidationError, match="username and password"):
        EmailNotificationConfig(
            name="ops-inbox",
            smtp_host="smtp.example.com",
            username="issuebot",
            from_email="issuebot@example.com",
            to_emails=["ops@example.com"],
        )


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
