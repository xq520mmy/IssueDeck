"""Pure Markdown renderer for per-branch changelogs."""

from __future__ import annotations

from collections import defaultdict

_KIND_HEADERS = {
    "feature": "Features",
    "bug": "Bugs",
    "improvement": "Improvements",
    "breaking": "Breaking",
    "infra": "Infrastructure",
    "research": "Research",
    "note": "Notes",
}


def render_changelog_markdown(
    *, project_name: str, branch_label: str, rows: list[dict],
) -> str:
    out: list[str] = [f"# {project_name} \u2014 {branch_label} Changelog", ""]

    if not rows:
        out.append("_no shipped items yet_")
        return "\n".join(out) + "\n"

    by_version: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_version[r["version"]][r["kind"]].append(r)

    for version in sorted(by_version.keys(), reverse=True):
        kinds = by_version[version]
        any_row = next(iter(next(iter(kinds.values()))))
        out.append(f"## {version}")
        out.append(f"_shipped {any_row['shipped_at']}_")
        out.append("")
        for kind_key in _KIND_HEADERS:
            if kind_key not in kinds:
                continue
            out.append(f"### {_KIND_HEADERS[kind_key]}")
            for r in kinds[kind_key]:
                line = f"- **{r['local_id']}** \u2014 {r['title']}"
                if r.get("commits"):
                    shas = ", ".join(f"`{c[:7]}`" for c in r["commits"])
                    line += f" ({shas})"
                out.append(line)
            out.append("")

    return "\n".join(out) + "\n"
