"""Built-in project templates for first-run project creation."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, model_validator

from issuedeck.core.config import CustomFieldConfig
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
    custom_fields: dict[str, CustomFieldConfig] = field(default_factory=dict)

    @property
    def kind_labels(self) -> tuple[str, ...]:
        return tuple(kind.label for kind in self.kinds)

    @property
    def status_labels(self) -> tuple[str, ...]:
        return tuple(status.label for status in self.statuses)

    @property
    def branch_labels(self) -> tuple[str, ...]:
        return tuple(branch.label for branch in self.branches)

    @property
    def custom_field_labels(self) -> tuple[str, ...]:
        return tuple(field.label for field in self.custom_fields.values())


@dataclass(frozen=True)
class ProjectTemplateValidationResult:
    path: Path
    ok: bool
    key: str | None = None
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectTemplatePackExample:
    key: str
    name: str
    description: str
    filename: str
    toml: str

    def to_project_template(self) -> ProjectTemplate:
        return load_project_template_from_toml(self.toml, source=self.filename)


DEFAULT_PROJECT_TEMPLATE_KEY = "basic"


def _custom_fields(*keys: str) -> dict[str, CustomFieldConfig]:
    field_defs = {
        "priority": CustomFieldConfig(
            label="Priority",
            type="select",
            options=["low", "medium", "high"],
        ),
        "estimate": CustomFieldConfig(label="Estimate", type="number"),
        "customer_impact": CustomFieldConfig(
            label="Customer impact",
            type="checkbox",
        ),
        "source_url": CustomFieldConfig(label="Source URL", type="url"),
        "component": CustomFieldConfig(
            label="Component",
            type="select",
            options=["frontend", "backend", "api", "docs", "infra"],
        ),
    }
    return {key: field_defs[key] for key in keys}


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
        custom_fields=_custom_fields("priority", "source_url"),
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
        custom_fields=_custom_fields(
            "priority",
            "estimate",
            "customer_impact",
            "source_url",
        ),
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
        custom_fields=_custom_fields(
            "priority",
            "estimate",
            "component",
            "source_url",
        ),
    ),
)

_PROJECT_TEMPLATE_MAP = {template.key: template for template in PROJECT_TEMPLATES}
_CUSTOM_FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


PROJECT_TEMPLATE_PACK_EXAMPLES: tuple[ProjectTemplatePackExample, ...] = (
    ProjectTemplatePackExample(
        key="support",
        name="Support queue",
        description="Customer requests, incidents, and escalation follow-up.",
        filename="support.toml",
        toml="""
key = "support"
name = "Support queue"
description = "Customer requests, incidents, and escalation follow-up."
ship_exempt_kinds = ["question"]

[custom_fields.priority]
label = "Priority"
type = "select"
options = ["low", "medium", "high", "urgent"]

[custom_fields.customer]
label = "Customer"
type = "text"

[custom_fields.source_url]
label = "Source URL"
type = "url"

[custom_fields.sla_risk]
label = "SLA risk"
type = "checkbox"

[[kinds]]
key = "question"
label = "Question"
prefix = "QST"

[[kinds]]
key = "incident"
label = "Incident"
prefix = "INC"

[[kinds]]
key = "request"
label = "Request"
prefix = "REQ"

[[statuses]]
key = "new"
label = "New"

[[statuses]]
key = "triaging"
label = "Triaging"

[[statuses]]
key = "waiting"
label = "Waiting"

[[statuses]]
key = "escalated"
label = "Escalated"

[[statuses]]
key = "resolved"
label = "Resolved"
terminal = true

[[statuses]]
key = "closed"
label = "Closed"
terminal = true

[[branches]]
key = "support"
label = "Support"
""".strip() + "\n",
    ),
    ProjectTemplatePackExample(
        key="content",
        name="Content calendar",
        description="Editorial planning from ideas through published assets.",
        filename="content.toml",
        toml="""
key = "content"
name = "Content calendar"
description = "Editorial planning from ideas through published assets."
ship_exempt_kinds = ["idea"]

[custom_fields.channel]
label = "Channel"
type = "select"
options = ["blog", "docs", "social", "video", "newsletter"]

[custom_fields.owner]
label = "Owner"
type = "text"

[custom_fields.publish_window]
label = "Publish window"
type = "text"

[custom_fields.source_url]
label = "Source URL"
type = "url"

[[kinds]]
key = "idea"
label = "Idea"
prefix = "IDEA"

[[kinds]]
key = "draft"
label = "Draft"
prefix = "DRFT"

[[kinds]]
key = "asset"
label = "Asset"
prefix = "AST"

[[statuses]]
key = "backlog"
label = "Backlog"

[[statuses]]
key = "drafting"
label = "Drafting"

[[statuses]]
key = "editing"
label = "Editing"

[[statuses]]
key = "scheduled"
label = "Scheduled"

[[statuses]]
key = "published"
label = "Published"
terminal = true
requires_ship = true

[[statuses]]
key = "archived"
label = "Archived"
terminal = true

[[branches]]
key = "website"
label = "Website"

[[branches]]
key = "newsletter"
label = "Newsletter"
""".strip() + "\n",
    ),
    ProjectTemplatePackExample(
        key="research",
        name="Research lab",
        description="Discovery, experiments, findings, and product decisions.",
        filename="research.toml",
        toml="""
key = "research"
name = "Research lab"
description = "Discovery, experiments, findings, and product decisions."

[custom_fields.confidence]
label = "Confidence"
type = "select"
options = ["low", "medium", "high"]

[custom_fields.effort]
label = "Effort"
type = "number"

[custom_fields.source_url]
label = "Source URL"
type = "url"

[[kinds]]
key = "question"
label = "Question"
prefix = "QST"

[[kinds]]
key = "experiment"
label = "Experiment"
prefix = "EXP"

[[kinds]]
key = "finding"
label = "Finding"
prefix = "FIND"

[[kinds]]
key = "decision"
label = "Decision"
prefix = "DEC"

[[statuses]]
key = "proposed"
label = "Proposed"

[[statuses]]
key = "researching"
label = "Researching"

[[statuses]]
key = "validating"
label = "Validating"

[[statuses]]
key = "synthesized"
label = "Synthesized"

[[statuses]]
key = "adopted"
label = "Adopted"
terminal = true

[[statuses]]
key = "archived"
label = "Archived"
terminal = true

[[branches]]
key = "research"
label = "Research"
""".strip() + "\n",
    ),
)

_PROJECT_TEMPLATE_PACK_EXAMPLE_MAP = {
    example.key: example for example in PROJECT_TEMPLATE_PACK_EXAMPLES
}


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
    custom_fields: dict[str, CustomFieldConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _cross_field_checks(self) -> ProjectTemplateFile:
        _ensure_unique([kind.key for kind in self.kinds], "kind")
        _ensure_unique([kind.prefix for kind in self.kinds], "kind prefix")
        _ensure_unique([status.key for status in self.statuses], "status")
        _ensure_unique([branch.key for branch in self.branches], "branch")
        for field_key in self.custom_fields:
            if not _CUSTOM_FIELD_KEY_RE.fullmatch(field_key):
                raise ValueError(
                    "custom field keys must start with a lowercase letter and "
                    "use lowercase letters, numbers, - or _"
                )

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
            custom_fields=self.custom_fields,
        )


def get_project_template(
    key: str,
    templates_dir: Path | str | None = None,
) -> ProjectTemplate | None:
    for template in list_project_templates(templates_dir):
        if template.key == key:
            return template
    return None


def get_project_template_pack_example(key: str) -> ProjectTemplatePackExample | None:
    return _PROJECT_TEMPLATE_PACK_EXAMPLE_MAP.get(key)


def list_project_template_pack_examples() -> tuple[ProjectTemplatePackExample, ...]:
    return PROJECT_TEMPLATE_PACK_EXAMPLES


def install_project_template_pack_example(
    key: str,
    templates_dir: Path | str,
    *,
    force: bool = False,
) -> Path:
    example = get_project_template_pack_example(key)
    if example is None:
        raise ConfigError(f"unknown project template pack example '{key}'")

    directory = Path(templates_dir)
    path = directory / example.filename
    if path.exists() and not force:
        raise ConfigError(f"project template pack example already exists: {path}")

    example.to_project_template()
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(example.toml, encoding="utf-8")
    return path


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


def validate_project_templates(
    templates_dir: Path | str,
) -> tuple[ProjectTemplateValidationResult, ...]:
    directory = Path(templates_dir)
    if not directory.exists():
        return ()
    if not directory.is_dir():
        return (
            ProjectTemplateValidationResult(
                path=directory,
                ok=False,
                errors=(f"project_templates_dir is not a directory: {directory}",),
            ),
        )

    results: list[ProjectTemplateValidationResult] = []
    seen = set(_PROJECT_TEMPLATE_MAP)
    for path in sorted(directory.glob("*.toml")):
        try:
            template = load_project_template(path)
        except ConfigError as exc:
            results.append(
                ProjectTemplateValidationResult(
                    path=path,
                    ok=False,
                    errors=(str(exc),),
                )
            )
            continue

        errors: list[str] = []
        if template.key in seen:
            errors.append(f"duplicate project template key '{template.key}'")
        else:
            seen.add(template.key)

        results.append(
            ProjectTemplateValidationResult(
                path=path,
                key=template.key,
                ok=not errors,
                errors=tuple(errors),
            )
        )
    return tuple(results)


def load_project_template(path: Path | str) -> ProjectTemplate:
    template_path = Path(path)
    try:
        text = template_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise ConfigError(f"project template not found: {template_path}") from exc

    return load_project_template_from_toml(text, source=str(template_path))


def load_project_template_from_toml(text: str, *, source: str) -> ProjectTemplate:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{source}: TOML parse error: {exc}") from exc

    try:
        return ProjectTemplateFile.model_validate(data).to_project_template()
    except ValidationError as exc:
        raise ConfigError(f"{source}: invalid project template: {exc}") from exc


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

    for field_key, cfg in template.custom_fields.items():
        lines.extend([
            f"[custom_fields.{field_key}]",
            f"label = {_toml_string(cfg.label)}",
            f"type = {_toml_string(cfg.type)}",
        ])
        if cfg.required:
            lines.append("required = true")
        if cfg.options:
            lines.append(f"options = {_toml_array(tuple(cfg.options))}")
        lines.append("")

    return "\n".join(lines)


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=False)
