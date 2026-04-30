"""Helpers for normalizing item external links."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal, TypedDict
from urllib.parse import urlparse

ExternalLinkType = Literal["github_issue", "github_pr", "github_commit", "other"]


class NormalizedExternalLink(TypedDict):
    link_type: ExternalLinkType
    label: str | None
    url: str


class GitHubReference(NormalizedExternalLink, total=False):
    owner: str
    repo: str
    number: int
    sha: str


_GITHUB_ISSUE_RE = re.compile(
    r"^/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>[1-9][0-9]*)/?$",
)
_GITHUB_PR_RE = re.compile(
    r"^/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>[1-9][0-9]*)/?$",
)
_GITHUB_COMMIT_RE = re.compile(
    r"^/(?P<owner>[^/]+)/(?P<repo>[^/]+)/commit/(?P<sha>[0-9a-fA-F]{7,64})/?$",
)


def normalize_external_link_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Fill inferred GitHub metadata while preserving explicit caller choices."""
    raw_url = raw.get("url")
    url = "" if raw_url is None else str(raw_url).strip()
    explicit_type = raw.get("link_type")
    link_type = explicit_type if explicit_type in _allowed_link_types() else None
    label = raw.get("label")
    clean_label = str(label).strip() if label is not None else None
    normalized = infer_external_link(url, label=clean_label, link_type=link_type)
    return {
        **dict(raw),
        "link_type": normalized["link_type"],
        "label": normalized["label"],
        "url": normalized["url"],
    }


def infer_external_link(
    url: str,
    *,
    label: str | None = None,
    link_type: ExternalLinkType | None = None,
) -> NormalizedExternalLink:
    clean_url = url.strip()
    inferred = _infer_github_link(clean_url)
    if inferred is None:
        return {
            "link_type": link_type or "other",
            "label": label or None,
            "url": clean_url,
        }

    final_type = link_type if link_type and link_type != "other" else inferred["link_type"]
    return {
        "link_type": final_type,
        "label": label or inferred["label"],
        "url": inferred["url"],
    }


def parse_github_reference(url: str) -> GitHubReference | None:
    """Parse a GitHub issue, pull request, or commit URL into stable metadata."""
    return _infer_github_link(url.strip())


def github_import_payload(
    url: str,
    *,
    kind: str,
    title: str | None = None,
    body: str | None = None,
    tags: list[str] | None = None,
    applies_to: list[str] | None = None,
    link_label: str | None = None,
) -> dict[str, Any]:
    ref = parse_github_reference(url)
    if ref is None:
        raise ValueError("URL must be a GitHub issue, pull request, or commit URL")

    default_title = _default_import_title(ref)
    default_body = "\n".join([
        "Linked from GitHub.",
        "",
        f"Source: {ref['url']}",
    ])
    payload: dict[str, Any] = {
        "kind": kind,
        "title": title or default_title,
        "body": body if body is not None else default_body,
        "tags": tags or ["github"],
        "external_links": [{
            "url": ref["url"],
            "link_type": ref["link_type"],
            "label": link_label or ref["label"],
        }],
    }
    if applies_to is not None:
        payload["applies_to"] = applies_to
    return payload


def _infer_github_link(url: str) -> GitHubReference | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None

    for pattern, link_type in (
        (_GITHUB_ISSUE_RE, "github_issue"),
        (_GITHUB_PR_RE, "github_pr"),
        (_GITHUB_COMMIT_RE, "github_commit"),
    ):
        match = pattern.fullmatch(parsed.path)
        if not match:
            continue
        data = match.groupdict()
        owner = data["owner"]
        repo = data["repo"]
        if link_type == "github_issue":
            number = data["number"]
            return {
                "link_type": "github_issue",
                "label": f"Issue #{number}",
                "url": f"https://github.com/{owner}/{repo}/issues/{number}",
                "owner": owner,
                "repo": repo,
                "number": int(number),
            }
        if link_type == "github_pr":
            number = data["number"]
            return {
                "link_type": "github_pr",
                "label": f"PR #{number}",
                "url": f"https://github.com/{owner}/{repo}/pull/{number}",
                "owner": owner,
                "repo": repo,
                "number": int(number),
            }
        sha = data["sha"]
        return {
            "link_type": "github_commit",
            "label": f"Commit {sha[:7]}",
            "url": f"https://github.com/{owner}/{repo}/commit/{sha}",
            "owner": owner,
            "repo": repo,
            "sha": sha,
        }
    return None


def _default_import_title(ref: GitHubReference) -> str:
    repo = f"{ref['owner']}/{ref['repo']}"
    if ref["link_type"] == "github_issue":
        return f"Review GitHub issue #{ref['number']} from {repo}"
    if ref["link_type"] == "github_pr":
        return f"Review GitHub PR #{ref['number']} from {repo}"
    return f"Review GitHub commit {ref['sha'][:7]} from {repo}"


def _allowed_link_types() -> set[str]:
    return {"github_issue", "github_pr", "github_commit", "other"}
