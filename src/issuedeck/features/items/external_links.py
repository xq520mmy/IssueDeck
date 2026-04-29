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


def _infer_github_link(url: str) -> NormalizedExternalLink | None:
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
            }
        if link_type == "github_pr":
            number = data["number"]
            return {
                "link_type": "github_pr",
                "label": f"PR #{number}",
                "url": f"https://github.com/{owner}/{repo}/pull/{number}",
            }
        sha = data["sha"]
        return {
            "link_type": "github_commit",
            "label": f"Commit {sha[:7]}",
            "url": f"https://github.com/{owner}/{repo}/commit/{sha}",
        }
    return None


def _allowed_link_types() -> set[str]:
    return {"github_issue", "github_pr", "github_commit", "other"}
