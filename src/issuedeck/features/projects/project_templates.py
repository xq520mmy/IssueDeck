"""Built-in project templates for first-run project creation."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, model_validator

from issuedeck.core.errors import ConfigError


@dataclass(frozen=True)
class KindTemplate:
    key: str
    label: str
    prefix: str


@dataclass(frozen=True)
class StatusTemplate:
    key: str
    label: str
    terminal: bool = False
    requires_ship: bool = False


@dataclass(frozen=True)
class BranchTemplate:
    key: str
    label: str


@dataclass(frozen=True)
class ProjectTemplate:
    key: str
    name_i18n: str
    description_i18n: str
    kinds: tuple[KindTemplate, ...]
    statuses: tuple[StatusTemplate, ...]
    branches: tuple[BranchTemplate, ...]
    ship_exempt_kinds: tuple[str, ...] = ()

    @property
    def kind_labels(self) -> tuple[str, ...]:
        return tuple(kind.label for kind in self.kinds)

    @property
    def status_labels(self) -> tuple[str, ...]:
        return tuple(status.label for status in self.statuses)

    @property
    def branch_labels(self) -> tuple[str, ...]:
        return tuple(branch.label for branch in self.branches)


DEFAULT_PROJECT_TEMPLATE_KEY = "basic"


PROJECT_TEMPLATES: tuple[ProjectTemplate, ...] = (
    ProjectTemplate(
        key="basic",
        name_i18n="project_template.basic.name",
        description_i18n="project_template.basic.description",
        kinds=(
            KindTemplate("feature", "Feature", "FEAT"),
            KindTemplate("bug", "Bug", "BUG"),
            KindTemplate("improvement", "Improvement", "IMP"),
        ),
        statuses=(
            StatusTemplate("proposed", "Proposed"),
            StatusTemplate("in_progress", "In Progress"),
            StatusTemplate("done", "Done", terminal=True, requires_ship=True),
            StatusTemplate("wontfix", "Won't Fix", terminal=True),
        ),
        branches=(BranchTemplate("main", "Main"),),
    ),
    ProjectTemplate(
        key="agent",
        name_i18n="project_template.agent.name",
        description_i18n="project_template.agent.description",
        kinds=(
            KindTemplate("feature", "Feature", "FEAT"),
            KindTemplate("bug", "Bug", "BUG"),
            KindTemplate("improvement", "Improvement", "IMP"),
            KindTemplate("task", "Task", "TASK"),
        ),
        statuses=(
            StatusTemplate("proposed", "Proposed"),
            StatusTemplate("in_progress", "In Progress"),
            StatusTemplate("blocked", "Blocked"),
            StatusTemplate("ready_to_ship", "Ready to Ship"),
            StatusTemplate("done", "Done", terminal=True, requires_ship=True),
            StatusTemplate("wontfix", "Won't Fix", terminal=True),
        ),
        branches=(BranchTemplate("main", "Main"),),
    ),
    ProjectTemplate(
        key="software",
        name_i18n="project_template.software.name",
        description_i18n="project_template.software.description",
        kinds=(
            KindTemplate("epic", "Epic", "EPIC"),
            KindTemplate("feature", "Feature", "FEAT"),
            KindTemplate("bug", "Bug", "BUG"),
            KindTemplate("chore", "Chore", "CHORE"),
        ),
        statuses=(
            StatusTemplate("backlog", "Backlog"),
            StatusTemplate("ready", "Ready"),
            StatusTemplate("in_progress", "In Progress"),
            StatusTemplate("review", "Review"),
            StatusTemplate("done", "Done", terminal=True, requires_ship=True),
            StatusTemplate("wontfix", "Won't Fix", terminal=True),
        ),
        branches=(
            BranchTemplate("main", "Main"),
            BranchTemplate("release", "Release"),
        ),
        ship_exempt_kinds=("chore",),
    ),
)

_PROJECT_TEMPLATE_MAP = {template.key: template for template in PROJECT_TEMPLATES}


def _ensure_unique(values: list[str], label: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate {label} '{value}'")
        seen.add(value)


class TemplateKindFile(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,62}$")
    label: str = Field(min_length=1, max_length=128)
    prefix: str = Field(pattern=r"^[A-Z][A-Z0-9]{1,9}$")


class TemplateStatusFile(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,62}$")
    label: str = Field(min_length=1, max_length=128)
    terminal: bool = False
    requires_ship: bool = False


class TemplateBranchFile(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,62}$")
    label: str = Field(min_length=1, max_length=128)


class ProjectTemplateFile(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,62}$")
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    kinds: list[TemplateKindFile] = Field(min_length=1)
    statuses: list[TemplateStatusFile] = Field(min_length=1)
    branches: list[TemplateBranchFile] = Field(default_factory=list)
    ship_exempt_kinds: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _cross_field_checks(self) -> ProjectTemplateFile:
        _ensure_unique([kind.key for kind in self.kinds], "kind")
        _ensure_unique([kind.prefix for kind in self.kinds], "kind prefix")
        _ensure_unique([status.key for status in self.statuses], "status")
        _ensure_unique([branch.key for branch in self.branches], "branch")

        kind_keys = {kind.key for kind in self.kinds}
        for kind in self.ship_exempt_kinds:
            if kind not in kind_keys:
                raise ValueError(f"ship_exempt_kinds references unknown kind '{kind}'")
        if any(status.requires_ship for status in self.statuses) and not self.branches:
            raise ValueError("requires_ship statuses need at least one branch")
        return self

    def to_project_template(self) -> ProjectTemplate:
        return ProjectTemplate(
            key=self.key,
            name_i18n=self.name,
            description_i18n=self.description,
            kinds=tuple(
                KindTemplate(kind.key, kind.label, kind.prefix)
                for kind in self.kinds
            ),
            statuses=tuple(
                StatusTemplate(
                    status.key,
                    status.label,
                    terminal=status.terminal,
                    requires_ship=status.requires_ship,
                )
                for status in self.statuses
            ),
            branches=tuple(
                BranchTemplate(branch.key, branch.label)
                for branch in self.branches
            ),
            ship_exempt_kinds=tuple(self.ship_exempt_kinds),
        )


def get_project_template(
    key: str,
    templates_dir: Path | str | None = None,
) -> ProjectTemplate | None:
    for template in list_project_templates(templates_dir):
        if template.key == key:
            return template
    return None


def list_project_templates(
    templates_dir: Path | str | None = None,
) -> tuple[ProjectTemplate, ...]:
    if templates_dir is None:
        return PROJECT_TEMPLATES
    return PROJECT_TEMPLATES + load_project_templates(templates_dir)


def load_project_templates(templates_dir: Path | str) -> tuple[ProjectTemplate, ...]:
    directory = Path(templates_dir)
    if not directory.exists():
        return ()
    if not directory.is_dir():
        raise ConfigError(f"project_templates_dir is not a directory: {directory}")

    templates: list[ProjectTemplate] = []
    seen = set(_PROJECT_TEMPLATE_MAP)
    for path in sorted(directory.glob("*.toml")):
        template = load_project_template(path)
        if template.key in seen:
            raise ConfigError(f"{path}: duplicate project template key '{template.key}'")
        seen.add(template.key)
        templates.append(template)
    return tuple(templates)


def load_project_template(path: Path | str) -> ProjectTemplate:
    template_path = Path(path)
    try:
        data = tomllib.loads(template_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ConfigError(f"project template not found: {template_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{template_path}: TOML parse error: {exc}") from exc

    try:
        return ProjectTemplateFile.model_validate(data).to_project_template()
    except ValidationError as exc:
        raise ConfigError(f"{template_path}: invalid project template: {exc}") from exc


def render_project_toml(
    *,
    key: str,
    name: str,
    description: str,
    template: ProjectTemplate,
) -> str:
    lines = [
        f"key = {_toml_string(key)}",
        f"name = {_toml_string(name)}",
        f"description = {_toml_string(description)}",
        "",
    ]

    for kind in template.kinds:
        lines.extend([
            f"[kinds.{kind.key}]",
            f"label = {_toml_string(kind.label)}",
            f"prefix = {_toml_string(kind.prefix)}",
            "",
        ])

    for status in template.statuses:
        lines.extend([
            f"[statuses.{status.key}]",
            f"label = {_toml_string(status.label)}",
        ])
        if status.terminal:
            lines.append("terminal = true")
        if status.requires_ship:
            lines.append("requires_ship = true")
        lines.append("")

    for branch in template.branches:
        lines.extend([
            "[[branches]]",
            f"key = {_toml_string(branch.key)}",
            f"label = {_toml_string(branch.label)}",
            "",
        ])

    lines.extend([
        "[id_format]",
        "digits = 4",
        "",
        "[ship_rules]",
        f"ship_exempt_kinds = {_toml_array(template.ship_exempt_kinds)}",
        "",
    ])
    return "\n".join(lines)


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=False)
