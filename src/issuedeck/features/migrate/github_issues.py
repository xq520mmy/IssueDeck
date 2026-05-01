"""Import GitHub repository issues into IssueDeck items."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from issuedeck.core.config import ConfigRegistry
from issuedeck.features.items.external_links import normalize_external_link_payload
from issuedeck.features.items.models import Item, ItemExternalLink
from issuedeck.features.items.repo import ItemRepo
from issuedeck.features.migrate.csv_items import (
    _dedupe,
    _default_statuses,
    _normalize_value,
    _resolve_branches,
    _resolve_status,
    _target_branches,
)

GITHUB_API_VERSION = "2022-11-28"


@dataclass(frozen=True)
class GitHubRepoRef:
    owner: str
    repo: str


@dataclass(frozen=True)
class GitHubIssueRow:
    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    html_url: str
    api_url: str
    author: str
    created_at: str
    updated_at: str
    comments: int
    is_pull_request: bool


@dataclass
class GitHubIssueImportReport:
    issues_fetched: int = 0
    pulls_skipped: int = 0
    existing_skipped: int = 0
    items_planned: int = 0
    items_written: int = 0
    status_mapped: int = 0
    external_links: int = 0


def parse_github_repo(value: str) -> GitHubRepoRef:
    """Accept `owner/repo` or a github.com repository URL."""
    clean = value.strip()
    if not clean:
        raise ValueError("GitHub repo is required")

    if "://" not in clean:
        parts = clean.strip("/").split("/")
        if len(parts) == 2 and all(parts):
            return GitHubRepoRef(owner=parts[0], repo=parts[1])
        raise ValueError("GitHub repo must be owner/repo or a https://github.com/owner/repo URL")

    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("GitHub repo URL must use http or https")
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("GitHub repo URL must point to github.com")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("GitHub repo URL must include owner and repo")
    return GitHubRepoRef(owner=parts[0], repo=parts[1].removesuffix(".git"))


async def fetch_github_issue_rows(
    repo: GitHubRepoRef,
    *,
    token: str | None = None,
    state: str = "open",
    labels: list[str] | None = None,
    since: str | None = None,
    limit: int = 50,
    include_pulls: bool = False,
    sort: str = "updated",
    direction: str = "desc",
    base_url: str = "https://api.github.com",
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[list[GitHubIssueRow], GitHubIssueImportReport]:
    """Fetch repository issues from GitHub REST API.

    GitHub's issues endpoint returns pull requests too, marked with a
    `pull_request` key. We filter those by default so importing issues does
    not unexpectedly create work items for PRs.
    """
    clean_limit = max(1, min(limit, 1000))
    report = GitHubIssueImportReport()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "IssueDeck",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    auth_token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    rows: list[GitHubIssueRow] = []
    page = 1
    max_pages = max(1, min(20, math.ceil(clean_limit / 100) + 10))
    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        headers=headers,
        timeout=20.0,
        transport=transport,
    ) as client:
        while len(rows) < clean_limit and page <= max_pages:
            params: dict[str, Any] = {
                "state": state,
                "sort": sort,
                "direction": direction,
                "per_page": min(100, clean_limit),
                "page": page,
            }
            if labels:
                params["labels"] = ",".join(labels)
            if since:
                params["since"] = since
            response = await client.get(
                f"/repos/{repo.owner}/{repo.repo}/issues",
                params=params,
            )
            _raise_for_github_error(response)
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("GitHub issues response must be a JSON array")
            if not payload:
                break
            for raw in payload:
                if not isinstance(raw, dict):
                    continue
                report.issues_fetched += 1
                is_pull_request = "pull_request" in raw
                if is_pull_request and not include_pulls:
                    report.pulls_skipped += 1
                    continue
                rows.append(_issue_row(raw))
                if len(rows) >= clean_limit:
                    break
            page += 1

    return rows, report


async def import_github_issue_rows(
    rows: list[GitHubIssueRow],
    project_key: str,
    registry: ConfigRegistry,
    db: AsyncSession,
    *,
    kind: str,
    default_status: str | None = None,
    tags: list[str] | None = None,
    applies_to: list[str] | None = None,
    status_map: dict[str, str] | None = None,
    dry_run: bool = False,
) -> GitHubIssueImportReport:
    project = registry.project(project_key)
    registry.validate_kind(project_key, kind)
    open_status, terminal_status = _default_statuses(project)
    fallback_status = default_status or open_status
    registry.validate_status(project_key, fallback_status)

    default_branches = _target_branches(project, applies_to)
    for branch in default_branches:
        registry.validate_branch(project_key, branch)

    raw_status_map = status_map or {}
    normalized_status_map = {
        _normalize_value(source): target for source, target in raw_status_map.items()
    }
    for target in normalized_status_map.values():
        registry.validate_status(project_key, target)

    report = GitHubIssueImportReport(issues_fetched=len(rows))
    existing_urls = await _existing_external_urls(
        db,
        project_key,
        [row.html_url for row in rows],
    )

    prepared: list[tuple[GitHubIssueRow, str, list[str]]] = []
    for row in rows:
        if row.html_url in existing_urls:
            report.existing_skipped += 1
            continue
        status, was_mapped = _resolve_status(
            row.state,
            project,
            default_status=fallback_status,
            terminal_status=terminal_status,
            status_map=normalized_status_map,
            row_number=row.number,
        )
        branches = _resolve_branches(
            [],
            project,
            default_branches=default_branches,
            row_number=row.number,
        )
        if was_mapped:
            report.status_mapped += 1
        prepared.append((row, status, branches))

    report.items_planned = len(prepared)
    report.external_links = len(prepared)
    if dry_run:
        return report

    repo = ItemRepo(db)
    for row, status, branches in prepared:
        kind_cfg = registry.validate_kind(project_key, kind)
        local_id = await repo.next_local_id(
            project_key,
            kind=kind,
            prefix=kind_cfg.prefix,
            digits=project.id_format.digits,
        )
        link = normalize_external_link_payload({
            "url": row.html_url,
            "link_type": "github_pr" if row.is_pull_request else "github_issue",
        })
        await repo.insert_item(
            project_key=project_key,
            local_id=local_id,
            kind=kind,
            status=status,
            title=row.title,
            body=_row_body(row),
            tags=_dedupe(["github", *(tags or []), *row.labels]),
            applies_to=branches,
            external_links=[{
                "link_type": str(link["link_type"]),
                "label": link.get("label"),
                "url": str(link["url"]),
            }],
        )
        report.items_written += 1

    await db.commit()
    return report


async def _existing_external_urls(
    db: AsyncSession,
    project_key: str,
    urls: list[str],
) -> set[str]:
    if not urls:
        return set()
    rows = (await db.execute(
        select(ItemExternalLink.url)
        .join(Item, Item.pk == ItemExternalLink.item_pk)
        .where(Item.project_key == project_key, ItemExternalLink.url.in_(urls))
    )).scalars().all()
    return set(rows)


def _issue_row(raw: dict[str, Any]) -> GitHubIssueRow:
    labels = raw.get("labels")
    label_names: list[str] = []
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, dict) and label.get("name"):
                label_names.append(str(label["name"]))
            elif isinstance(label, str):
                label_names.append(label)

    return GitHubIssueRow(
        number=int(raw.get("number") or 0),
        title=str(raw.get("title") or f"GitHub issue #{raw.get('number') or 0}").strip(),
        body=str(raw.get("body") or "").strip(),
        state=str(raw.get("state") or "open").strip(),
        labels=_dedupe(label_names),
        html_url=str(raw.get("html_url") or "").strip(),
        api_url=str(raw.get("url") or "").strip(),
        author=_login(raw.get("user")),
        created_at=str(raw.get("created_at") or "").strip(),
        updated_at=str(raw.get("updated_at") or "").strip(),
        comments=int(raw.get("comments") or 0),
        is_pull_request="pull_request" in raw,
    )


def _login(value: object) -> str:
    if isinstance(value, dict):
        login = value.get("login")
        return str(login).strip() if login else ""
    return ""


def _row_body(row: GitHubIssueRow) -> str:
    lines: list[str] = []
    if row.body:
        lines.extend([row.body, ""])
    lines.extend([
        "Imported from GitHub Issues.",
        "",
        f"Source: {row.html_url}",
        f"GitHub number: #{row.number}",
        f"State: {row.state}",
    ])
    if row.author:
        lines.append(f"Author: {row.author}")
    if row.created_at:
        lines.append(f"GitHub created: {row.created_at}")
    if row.updated_at:
        lines.append(f"GitHub updated: {row.updated_at}")
    lines.append(f"GitHub comments: {row.comments}")
    return "\n".join(lines)


def _raise_for_github_error(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    try:
        payload = response.json()
    except Exception:
        payload = {}
    message = payload.get("message") if isinstance(payload, dict) else None
    if not message:
        message = response.text or f"GitHub API returned HTTP {response.status_code}"
    raise ValueError(f"GitHub API error ({response.status_code}): {message}")
