"""Config loading — ServerConfig + ProjectConfig + ConfigRegistry.

TOML is parsed via stdlib `tomllib`. Env vars with the ISSUEDECK_ prefix override
server.toml values so secrets can live outside the repo. Project TOMLs live in
`projects_dir` and are loaded at startup; `ConfigRegistry` is read-only after
construction.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, model_validator

from issuedeck.core.errors import (
    ConfigError,
    InvalidBranch,
    InvalidKind,
    InvalidStatus,
    ProjectNotFound,
)


class SqliteConfig(BaseModel):
    wal_mode: bool = True
    busy_timeout_ms: int = 5000


TokenScope = Literal["read", "read-only", "agent", "admin"]


class TokenConfig(BaseModel):
    name: str
    token: SecretStr
    scopes: list[TokenScope]

    @model_validator(mode="after")
    def _validate_scopes(self) -> TokenConfig:
        if not self.scopes:
            raise ValueError("token scopes must not be empty")
        return self

    def normalized_scopes(self) -> set[str]:
        return {"read" if scope == "read-only" else scope for scope in self.scopes}


WebhookEvent = Literal[
    "item.created",
    "item.updated",
    "item.shipped",
    "item.deleted",
    "item.restored",
]
NotificationProvider = Literal["slack", "discord"]
EmailSecurity = Literal["starttls", "ssl", "none"]

DEFAULT_WEBHOOK_EVENTS: list[WebhookEvent] = [
    "item.created",
    "item.updated",
    "item.shipped",
    "item.deleted",
    "item.restored",
]


class WebhookConfig(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    url: str = Field(min_length=1, max_length=2048)
    secret: SecretStr
    events: list[WebhookEvent] = Field(default_factory=lambda: DEFAULT_WEBHOOK_EVENTS.copy())
    retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    backoff_seconds: float = Field(default=0.5, ge=0, le=10)

    @model_validator(mode="after")
    def _validate_events(self) -> WebhookConfig:
        if not self.events:
            raise ValueError("webhook events must not be empty")
        return self


class NotificationConfig(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    provider: NotificationProvider
    url: SecretStr = Field(min_length=1, max_length=2048)
    events: list[WebhookEvent] = Field(default_factory=lambda: DEFAULT_WEBHOOK_EVENTS.copy())
    retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    backoff_seconds: float = Field(default=0.5, ge=0, le=10)

    @model_validator(mode="after")
    def _validate_events(self) -> NotificationConfig:
        if not self.events:
            raise ValueError("notification events must not be empty")
        return self


class EmailNotificationConfig(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    smtp_host: str = Field(min_length=1, max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: EmailSecurity = "starttls"
    username: str | None = Field(default=None, min_length=1, max_length=255)
    password: SecretStr | None = None
    from_email: str = Field(min_length=1, max_length=255)
    to_emails: list[str] = Field(min_length=1)
    subject_prefix: str = Field(default="[IssueDeck]", min_length=1, max_length=80)
    events: list[WebhookEvent] = Field(default_factory=lambda: DEFAULT_WEBHOOK_EVENTS.copy())
    retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    backoff_seconds: float = Field(default=0.5, ge=0, le=10)

    @model_validator(mode="after")
    def _validate_email_notification(self) -> EmailNotificationConfig:
        if not self.events:
            raise ValueError("email notification events must not be empty")
        if bool(self.username) != bool(self.password):
            raise ValueError("email notification username and password must be set together")
        values = [
            self.smtp_host,
            self.from_email,
            self.subject_prefix,
            *self.to_emails,
        ]
        if any("\r" in value or "\n" in value for value in values):
            raise ValueError("email notification fields must not contain newlines")
        if any(not email.strip() for email in self.to_emails):
            raise ValueError("email notification recipients must not be empty")
        return self


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8765
    api_token: SecretStr
    tokens: list[TokenConfig] = Field(default_factory=list)
    data_dir: Path = Path("./data")
    projects_dir: Path = Path("./projects")
    project_templates_dir: Path = Path("./project-templates")
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    sqlite: SqliteConfig = SqliteConfig()
    webhooks: list[WebhookConfig] = Field(default_factory=list)
    notifications: list[NotificationConfig] = Field(default_factory=list)
    email_notifications: list[EmailNotificationConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _env_overrides(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if tok := os.environ.get("ISSUEDECK_API_TOKEN"):
            data["api_token"] = tok
        if h := os.environ.get("ISSUEDECK_HOST"):
            data["host"] = h
        if p := os.environ.get("ISSUEDECK_PORT"):
            data["port"] = int(p)
        if d := os.environ.get("ISSUEDECK_DATA_DIR"):
            data["data_dir"] = d
        if pd := os.environ.get("ISSUEDECK_PROJECTS_DIR"):
            data["projects_dir"] = pd
        if td := os.environ.get("ISSUEDECK_PROJECT_TEMPLATES_DIR"):
            data["project_templates_dir"] = td
        return data

    @model_validator(mode="after")
    def _validate_tokens(self) -> ServerConfig:
        seen_names = {"api_token"}
        seen_values = {self.api_token.get_secret_value()}
        for token in self.tokens:
            if token.name in seen_names:
                raise ValueError(f"duplicate token name '{token.name}'")
            seen_names.add(token.name)
            value = token.token.get_secret_value()
            if value in seen_values:
                raise ValueError(f"duplicate token value for '{token.name}'")
            seen_values.add(value)
        return self

    @model_validator(mode="after")
    def _validate_webhooks(self) -> ServerConfig:
        seen_names: set[str] = set()
        for webhook in self.webhooks:
            if webhook.name in seen_names:
                raise ValueError(f"duplicate webhook name '{webhook.name}'")
            seen_names.add(webhook.name)
        return self

    @model_validator(mode="after")
    def _validate_notifications(self) -> ServerConfig:
        seen_names: set[str] = set()
        for notification in self.notifications:
            if notification.name in seen_names:
                raise ValueError(f"duplicate notification name '{notification.name}'")
            seen_names.add(notification.name)
        return self

    @model_validator(mode="after")
    def _validate_email_notifications(self) -> ServerConfig:
        seen_names: set[str] = set()
        for notification in self.email_notifications:
            if notification.name in seen_names:
                raise ValueError(f"duplicate email notification name '{notification.name}'")
            seen_names.add(notification.name)
        return self

    def auth_tokens(self) -> list[TokenConfig]:
        legacy_admin = TokenConfig(
            name="api_token",
            token=self.api_token,
            scopes=["admin"],
        )
        return [legacy_admin, *self.tokens]


class KindConfig(BaseModel):
    label: str
    prefix: str = Field(pattern=r"^[A-Z][A-Z0-9]{1,9}$")


class StatusConfig(BaseModel):
    label: str
    terminal: bool = False
    requires_ship: bool = False


class BranchConfig(BaseModel):
    key: str
    label: str
    changelog_path: Path | None = None


class IdFormat(BaseModel):
    digits: int = Field(default=4, ge=2, le=8)


class ShipRules(BaseModel):
    ship_exempt_kinds: list[str] = []


class ProjectConfig(BaseModel):
    key: str
    name: str
    description: str = ""
    kinds: dict[str, KindConfig]
    statuses: dict[str, StatusConfig]
    branches: list[BranchConfig] = []
    id_format: IdFormat = IdFormat()
    ship_rules: ShipRules = ShipRules()

    @model_validator(mode="after")
    def _cross_field_checks(self) -> ProjectConfig:
        if not self.kinds:
            raise ValueError("kinds must not be empty")
        if not self.statuses:
            raise ValueError("statuses must not be empty")

        for k in self.ship_rules.ship_exempt_kinds:
            if k not in self.kinds:
                raise ValueError(f"ship_exempt_kinds references unknown kind '{k}'")

        if any(s.requires_ship for s in self.statuses.values()) and not self.branches:
            raise ValueError(
                "a status declares requires_ship=true but [[branches]] is empty"
            )

        prefixes = [k.prefix for k in self.kinds.values()]
        if len(set(prefixes)) != len(prefixes):
            raise ValueError(f"duplicate kind.prefix values: {prefixes}")

        bkeys = [b.key for b in self.branches]
        if len(set(bkeys)) != len(bkeys):
            raise ValueError(f"duplicate branch keys: {bkeys}")

        return self


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as e:
        raise ConfigError(f"config file not found: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: TOML parse error: {e}") from e


def load_server_config(path: Path) -> ServerConfig:
    data = _read_toml(path)
    return ServerConfig.model_validate(data)


def load_project_config(path: Path) -> ProjectConfig:
    data = _read_toml(path)
    return ProjectConfig.model_validate(data)


class ConfigRegistry:
    """Singleton, constructed at startup, read-only afterward."""

    def __init__(self, server: ServerConfig, projects: dict[str, ProjectConfig]):
        self._server = server
        self._projects = projects

    @property
    def server(self) -> ServerConfig:
        return self._server

    def project(self, key: str) -> ProjectConfig:
        try:
            return self._projects[key]
        except KeyError as exc:
            raise ProjectNotFound(
                f"project '{key}' not found", details={"project_key": key}
            ) from exc

    def all_projects(self) -> list[ProjectConfig]:
        return list(self._projects.values())

    def register_project(self, project: ProjectConfig) -> None:
        if project.key in self._projects:
            raise ConfigError(f"duplicate project key '{project.key}'")
        self._projects[project.key] = project

    def validate_kind(self, project_key: str, kind: str) -> KindConfig:
        pc = self.project(project_key)
        if kind not in pc.kinds:
            raise InvalidKind(
                f"kind '{kind}' is not defined in project '{project_key}'",
                details={"project_key": project_key, "kind": kind,
                         "valid": sorted(pc.kinds.keys())},
            )
        return pc.kinds[kind]

    def validate_status(self, project_key: str, status: str) -> StatusConfig:
        pc = self.project(project_key)
        if status not in pc.statuses:
            raise InvalidStatus(
                f"status '{status}' is not defined in project '{project_key}'",
                details={"project_key": project_key, "status": status,
                         "valid": sorted(pc.statuses.keys())},
            )
        return pc.statuses[status]

    def validate_branch(self, project_key: str, branch_key: str) -> BranchConfig:
        pc = self.project(project_key)
        for b in pc.branches:
            if b.key == branch_key:
                return b
        raise InvalidBranch(
            f"branch '{branch_key}' is not defined in project '{project_key}'",
            details={"project_key": project_key, "branch_key": branch_key,
                     "valid": [b.key for b in pc.branches]},
        )
