"""Import plain Markdown task lists into IssueDeck items."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from issuedeck.core.config import ConfigRegistry, ProjectConfig
from issuedeck.features.items.external_links import normalize_external_link_payload
from issuedeck.features.items.repo import ItemRepo

_TASK_RE = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])\s+\[(?P<mark>[ xX])\]\s+(?P<title>.+?)\s*$"
)
_URL_RE = re.compile(r"https?://[^\s<>\]\)]+")


@dataclass(frozen=True)
class MarkdownTask:
    title: str
    checked: bool
    source_path: str
    line_number: int
    notes: list[str]
    external_links: list[dict[str, str | None]]


@dataclass
class MarkdownTaskImportReport:
    tasks_found: int = 0
    items_planned: int = 0
    items_written: int = 0
    checked_tasks: int = 0
    skipped_checked: int = 0
    external_links: int = 0


def parse_markdown_task_list(
    source: Path,
    *,
    include_checked: bool = False,
) -> tuple[list[MarkdownTask], MarkdownTaskImportReport]:
    """Parse GitHub-style Markdown task lists from one file or a directory."""
    files = _markdown_files(source)
    tasks: list[MarkdownTask] = []
    report = MarkdownTaskImportReport()

    for path in files:
        rel = _display_path(path, source)
        parsed, file_report = _parse_task_file(
            path.read_text(encoding="utf-8"),
            rel,
            include_checked=include_checked,
        )
        tasks.extend(parsed)
        report.tasks_found += file_report.tasks_found
        report.checked_tasks += file_report.checked_tasks
        report.skipped_checked += file_report.skipped_checked

    report.items_planned = len(tasks)
    report.external_links = sum(len(task.external_links) for task in tasks)
    return tasks, report


async def import_markdown_task_list(
    source: Path,
    project_key: str,
    registry: ConfigRegistry,
    db: AsyncSession,
    *,
    kind: str,
    tags: list[str] | None = None,
    applies_to: list[str] | None = None,
    include_checked: bool = False,
    dry_run: bool = False,
) -> MarkdownTaskImportReport:
    project = registry.project(project_key)
    registry.validate_kind(project_key, kind)
    open_status, checked_status = _default_task_statuses(project)
    branches = _target_branches(project, applies_to)
    for branch in branches:
        registry.validate_branch(project_key, branch)

    tasks, report = parse_markdown_task_list(source, include_checked=include_checked)
    if dry_run:
        return report

    repo = ItemRepo(db)
    kind_cfg = registry.validate_kind(project_key, kind)
    import_tags = _dedupe(["markdown", *(tags or [])])
    for task in tasks:
        local_id = await repo.next_local_id(
            project_key,
            kind=kind,
            prefix=kind_cfg.prefix,
            digits=project.id_format.digits,
        )
        status = checked_status if task.checked else open_status
        await repo.insert_item(
            project_key=project_key,
            local_id=local_id,
            kind=kind,
            status=status,
            title=task.title,
            body=_task_body(task),
            tags=import_tags,
            applies_to=branches,
            external_links=task.external_links,
        )
        report.items_written += 1

    await db.commit()
    return report


def _parse_task_file(
    text: str,
    source_path: str,
    *,
    include_checked: bool,
) -> tuple[list[MarkdownTask], MarkdownTaskImportReport]:
    tasks: list[MarkdownTask] = []
    report = MarkdownTaskImportReport()
    current: dict[str, object] | None = None

    def finish() -> None:
        nonlocal current
        if current is None:
            return
        title = str(current["title"])
        notes = list(current["notes"])  # type: ignore[arg-type]
        tasks.append(MarkdownTask(
            title=title,
            checked=bool(current["checked"]),
            source_path=source_path,
            line_number=int(current["line_number"]),
            notes=notes,
            external_links=_external_links_for_task(title, notes),
        ))
        current = None

    for line_number, line in enumerate(text.splitlines(), start=1):
        match = _TASK_RE.match(line)
        if match:
            finish()
            report.tasks_found += 1
            checked = match.group("mark").lower() == "x"
            if checked:
                report.checked_tasks += 1
            if checked and not include_checked:
                report.skipped_checked += 1
                current = None
                continue
            title = _clean_title(match.group("title"))
            if not title:
                current = None
                continue
            current = {
                "title": title,
                "checked": checked,
                "line_number": line_number,
                "notes": [],
            }
            continue

        if current is not None and _is_continuation(line):
            note = line.strip()
            if note:
                current["notes"].append(note)  # type: ignore[index,union-attr]
            continue

        if current is not None and line.strip():
            finish()

    finish()
    report.items_planned = len(tasks)
    report.external_links = sum(len(task.external_links) for task in tasks)
    return tasks, report


def _markdown_files(source: Path) -> list[Path]:
    if source.is_file():
        if source.suffix.lower() != ".md":
            raise ValueError(f"source file must be Markdown: {source}")
        return [source]
    if source.is_dir():
        return sorted(
            path
            for path in source.rglob("*.md")
            if not any(part.startswith(".") for part in path.relative_to(source).parts)
        )
    raise ValueError(f"source path not found: {source}")


def _display_path(path: Path, source: Path) -> str:
    if source.is_dir():
        return path.relative_to(source).as_posix()
    return path.name


def _clean_title(raw: str) -> str:
    return raw.strip().removeprefix("-").strip()


def _is_continuation(line: str) -> bool:
    return line.startswith(("  ", "\t")) and _TASK_RE.match(line) is None


def _external_links_for_task(
    title: str,
    notes: list[str],
) -> list[dict[str, str | None]]:
    raw_text = "\n".join([title, *notes])
    links: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for url in _URL_RE.findall(raw_text):
        normalized = normalize_external_link_payload({"url": url})
        normalized_url = str(normalized["url"])
        if normalized_url in seen:
            continue
        seen.add(normalized_url)
        links.append({
            "link_type": str(normalized["link_type"]),
            "label": normalized.get("label"),
            "url": normalized_url,
        })
    return links


def _default_task_statuses(project: ProjectConfig) -> tuple[str, str]:
    open_status = next(
        (key for key, cfg in project.statuses.items() if not cfg.terminal),
        next(iter(project.statuses.keys())),
    )
    checked_status = next(
        (key for key, cfg in project.statuses.items() if cfg.terminal),
        open_status,
    )
    return open_status, checked_status


def _target_branches(project: ProjectConfig, applies_to: list[str] | None) -> list[str]:
    if applies_to is not None:
        return applies_to
    return [branch.key for branch in project.branches]


def _task_body(task: MarkdownTask) -> str:
    lines = [
        "Imported from a Markdown task list.",
        "",
        f"Source: {task.source_path}:{task.line_number}",
    ]
    if task.checked:
        lines.append("Original state: checked")
    if task.notes:
        lines.extend(["", *task.notes])
    return "\n".join(lines)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        clean = value.strip()
        if clean and clean not in result:
            result.append(clean)
    return result
