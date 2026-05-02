"""Built-in project templates for first-run project creation."""

from __future__ import annotations

import json
from dataclasses import dataclass


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


def get_project_template(key: str) -> ProjectTemplate | None:
    return _PROJECT_TEMPLATE_MAP.get(key)


def list_project_templates() -> tuple[ProjectTemplate, ...]:
    return PROJECT_TEMPLATES


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
