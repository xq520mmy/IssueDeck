"""CLI entry point. Subcommands for local demo, server, import, export, and MCP."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_DEMO_TOKEN = "issuedeck-local-token"

_DEMO_PROJECT_TOML = """key = "example"
name = "Example Project"
description = "A fake project config for demos, screenshots, and first-run trials."

[kinds.feature]
label = "Feature"
prefix = "FEAT"

[kinds.bug]
label = "Bug"
prefix = "BUG"

[kinds.improvement]
label = "Improvement"
prefix = "IMP"

[statuses.proposed]
label = "Proposed"

[statuses.in_progress]
label = "In Progress"

[statuses.done]
label = "Done"
terminal = true
requires_ship = true

[statuses.wontfix]
label = "Won't Fix"
terminal = true

[[branches]]
key = "main"
label = "Main"

[id_format]
digits = 4

[ship_rules]
ship_exempt_kinds = []
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="issuedeck")
    sub = parser.add_subparsers(dest="cmd")

    p_demo = sub.add_parser(
        "demo",
        help="Create a local demo config, seed fake data, and run the dashboard",
    )
    p_demo.add_argument("--config", default="server.toml")
    p_demo.add_argument("--project-key", default="example")
    p_demo.add_argument("--host", default=None)
    p_demo.add_argument("--port", type=int, default=None)
    p_demo.add_argument(
        "--force-reset-demo-data",
        action="store_true",
        help="Replace existing items in the demo project before seeding",
    )
    p_demo.add_argument("--open", action="store_true", help="Open the dashboard in a browser")

    p_serve = sub.add_parser("serve", help="Run FastAPI server via uvicorn")
    p_serve.add_argument("--config", default="server.toml")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)

    p_mig = sub.add_parser("migrate", help="Migrate markdown frontmatter into issuedeck")
    p_mig.add_argument("--config", default="server.toml")
    p_mig.add_argument(
        "--from-frontmatter",
        required=True,
        help="Path to a directory containing items/*.md frontmatter files",
    )
    p_mig.add_argument("--project-key", required=True)
    p_mig.add_argument("--dry-run", action="store_true")
    p_mig.add_argument("--force-reset", action="store_true")
    p_mig.add_argument(
        "--preset",
        action="append",
        default=[],
        choices=["generic", "github", "linear"],
        help="Apply a named frontmatter adapter preset before custom aliases",
    )
    p_mig.add_argument(
        "--field-alias",
        action="append",
        default=[],
        metavar="FIELD=ALIAS[,ALIAS...]",
        help=(
            "Add frontmatter field aliases, e.g. kind=category, "
            "status=workflow, tags=keywords"
        ),
    )

    p_exp = sub.add_parser("export", help="Export project as markdown bundle")
    p_exp.add_argument("--config", default="server.toml")
    p_exp.add_argument("--project-key", required=True)
    p_exp.add_argument("--out", required=True, help="Output directory")

    p_audit = sub.add_parser(
        "export-audit-bundle",
        help="Export a project audit snapshot as a ZIP bundle",
    )
    p_audit.add_argument("--config", default="server.toml")
    p_audit.add_argument("--project-key", required=True)
    p_audit.add_argument(
        "--out",
        required=True,
        help="Output .zip path, or a directory for <project>-audit-bundle.zip",
    )

    p_seed = sub.add_parser("seed-demo", help="Seed fake demo data for docs/screenshots")
    p_seed.add_argument("--config", default="server.toml")
    p_seed.add_argument("--project-key", default="example")
    p_seed.add_argument("--force-reset", action="store_true")

    p_create = sub.add_parser("create-item", help="Create an item in the local database")
    p_create.add_argument("--config", default="server.toml")
    p_create.add_argument("--project-key", required=True)
    p_create.add_argument(
        "--kind",
        default=None,
        help="IssueDeck kind to create; defaults to the first kind in the project config",
    )
    p_create.add_argument("--title", required=True)
    body_group = p_create.add_mutually_exclusive_group()
    body_group.add_argument("--body", default=None, help="Item body text")
    body_group.add_argument(
        "--body-file",
        default=None,
        help="Read item body from a UTF-8 file, or '-' for stdin",
    )
    p_create.add_argument("--tag", action="append", default=[], help="Add a tag")
    p_create.add_argument(
        "--applies-to",
        action="append",
        default=None,
        metavar="BRANCH",
        help="Target branch; repeat for multiple branches",
    )
    p_create.add_argument(
        "--custom-field",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="Set a project custom field; repeat for multiple fields",
    )
    p_create.add_argument(
        "--external-link",
        action="append",
        default=[],
        metavar="LINK",
        help="Attach an external link; accepts URL or 'Label | URL'",
    )
    p_create.add_argument("--dry-run", action="store_true", help="Print the create payload only")
    p_create.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format after creation",
    )

    p_update = sub.add_parser("update-item", help="Update an item in the local database")
    p_update.add_argument("local_id", help="Item local ID, for example FEAT-0001")
    p_update.add_argument("--config", default="server.toml")
    p_update.add_argument("--project-key", required=True)
    p_update.add_argument("--title", default=None)
    p_update.add_argument("--status", default=None)
    update_body_group = p_update.add_mutually_exclusive_group()
    update_body_group.add_argument("--body", default=None, help="Replace item body text")
    update_body_group.add_argument(
        "--body-file",
        default=None,
        help="Replace item body from a UTF-8 file, or '-' for stdin",
    )
    update_body_group.add_argument(
        "--append-body",
        default=None,
        help="Append text to the current item body",
    )
    update_body_group.add_argument(
        "--append-body-file",
        default=None,
        help="Append text from a UTF-8 file, or '-' for stdin",
    )
    p_update.add_argument(
        "--tag",
        action="append",
        default=None,
        help="Replace tags; repeat for multiple tags",
    )
    p_update.add_argument(
        "--applies-to",
        action="append",
        default=None,
        metavar="BRANCH",
        help="Replace target branches; repeat for multiple branches",
    )
    p_update.add_argument(
        "--custom-field",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="Set or clear a project custom field; use FIELD= to clear",
    )
    p_update.add_argument(
        "--external-link",
        action="append",
        default=None,
        metavar="LINK",
        help="Replace external links; accepts URL or 'Label | URL'",
    )
    p_update.add_argument(
        "--clear-external-links",
        action="store_true",
        help="Remove all external links from the item",
    )
    p_update.add_argument("--dry-run", action="store_true", help="Print the update payload only")
    p_update.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format after update",
    )

    p_bulk = sub.add_parser(
        "bulk-update-items",
        help="Update, delete, or restore multiple local items",
    )
    p_bulk.add_argument("local_ids", nargs="+", help="Item local IDs, for example FEAT-0001")
    p_bulk.add_argument("--config", default="server.toml")
    p_bulk.add_argument("--project-key", required=True)
    p_bulk.add_argument(
        "--action",
        choices=["update", "delete", "restore"],
        default="update",
    )
    p_bulk.add_argument("--kind", default=None)
    p_bulk.add_argument("--status", default=None)
    p_bulk.add_argument(
        "--tag",
        action="append",
        default=None,
        help="Tag to add/remove/replace; repeat for multiple tags",
    )
    p_bulk.add_argument(
        "--tag-mode",
        choices=["add", "remove", "replace"],
        default="add",
    )
    p_bulk.add_argument(
        "--applies-to",
        action="append",
        default=None,
        metavar="BRANCH",
        help="Replace target branches; repeat for multiple branches",
    )
    p_bulk.add_argument(
        "--custom-field",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="Set or clear a project custom field; use FIELD= to clear",
    )
    p_bulk.add_argument("--reason", default="cli bulk update")
    p_bulk.add_argument("--dry-run", action="store_true", help="Print the bulk payload only")
    p_bulk.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format after bulk update",
    )

    p_ship = sub.add_parser("ship-item", help="Mark a local item as shipped")
    p_ship.add_argument("local_id", help="Item local ID, for example FEAT-0001")
    p_ship.add_argument("--config", default="server.toml")
    p_ship.add_argument("--project-key", required=True)
    p_ship.add_argument("--branch", required=True)
    p_ship.add_argument("--version", required=True)
    p_ship.add_argument(
        "--commit",
        action="append",
        default=[],
        help="Commit SHA to attach to the ship record; repeat for multiple commits",
    )
    p_ship.add_argument("--dry-run", action="store_true", help="Print the ship payload only")
    p_ship.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format after shipping",
    )

    p_event = sub.add_parser(
        "append-item-event",
        help="Append a timeline event or comment to a local item",
    )
    p_event.add_argument("local_id", help="Item local ID, for example FEAT-0001")
    p_event.add_argument("--config", default="server.toml")
    p_event.add_argument("--project-key", required=True)
    event_body_group = p_event.add_mutually_exclusive_group(required=True)
    event_body_group.add_argument("--body", default=None, help="Event body text")
    event_body_group.add_argument(
        "--body-file",
        default=None,
        help="Read event body from a UTF-8 file, or '-' for stdin",
    )
    p_event.add_argument("--event-type", default="comment")
    p_event.add_argument(
        "--actor-type",
        choices=["human", "agent", "system"],
        default="human",
    )
    p_event.add_argument("--actor-name", default="cli")
    p_event.add_argument(
        "--metadata",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Attach event metadata; repeat for multiple values",
    )
    p_event.add_argument("--dry-run", action="store_true", help="Print the event payload only")
    p_event.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format after appending the event",
    )

    p_list = sub.add_parser("list-items", help="List project items from the local database")
    p_list.add_argument("--config", default="server.toml")
    p_list.add_argument("--project-key", required=True)
    p_list.add_argument("--kind", action="append", default=[], help="Filter by kind")
    p_list.add_argument("--status", action="append", default=[], help="Filter by status")
    p_list.add_argument("--tag", action="append", default=[], help="Filter by tag")
    p_list.add_argument(
        "--applies-to",
        action="append",
        default=[],
        metavar="BRANCH",
        help="Filter by target branch; repeat for multiple branches",
    )
    p_list.add_argument(
        "--relation-type",
        action="append",
        default=[],
        help="Filter by relationship type, e.g. blocked_by",
    )
    p_list.add_argument(
        "--custom-field",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="Filter by custom field; supports FIELD=VALUE, FIELD>=VALUE, FIELD:missing",
    )
    p_list.add_argument("--include-deleted", action="store_true")
    p_list.add_argument("--only-deleted", action="store_true")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format",
    )

    p_get = sub.add_parser("get-item", help="Show a single project item")
    p_get.add_argument("local_id", help="Item local ID, for example FEAT-0001")
    p_get.add_argument("--config", default="server.toml")
    p_get.add_argument("--project-key", required=True)
    p_get.add_argument("--include-deleted", action="store_true")
    p_get.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    p_gh = sub.add_parser(
        "import-github-url",
        help="Create an item linked to a GitHub issue, pull request, or commit URL",
    )
    p_gh.add_argument("url", help="GitHub issue, pull request, or commit URL")
    p_gh.add_argument("--config", default="server.toml")
    p_gh.add_argument("--project-key", required=True)
    p_gh.add_argument(
        "--kind",
        default=None,
        help="IssueDeck kind to create; defaults to the first kind in the project config",
    )
    p_gh.add_argument("--title", default=None, help="Override the generated item title")
    p_gh.add_argument("--body", default=None, help="Override the generated item body")
    p_gh.add_argument("--tag", action="append", default=[], help="Add a tag")
    p_gh.add_argument(
        "--applies-to",
        action="append",
        default=None,
        metavar="BRANCH",
        help="Target branch; repeat for multiple branches",
    )
    p_gh.add_argument("--link-label", default=None, help="Override the external link label")
    p_gh.add_argument("--dry-run", action="store_true", help="Print the create payload only")

    p_gh_issues = sub.add_parser(
        "import-github-issues",
        help="Import issues from a GitHub repository without creating duplicates",
    )
    p_gh_issues.add_argument("repo", help="GitHub owner/repo or repository URL")
    p_gh_issues.add_argument("--config", default="server.toml")
    p_gh_issues.add_argument("--project-key", required=True)
    p_gh_issues.add_argument(
        "--kind",
        default=None,
        help="IssueDeck kind to create; defaults to the first kind in the project config",
    )
    p_gh_issues.add_argument(
        "--default-status",
        default=None,
        help="Status for open issues; defaults to the first non-terminal status",
    )
    p_gh_issues.add_argument("--tag", action="append", default=[], help="Add a tag")
    p_gh_issues.add_argument(
        "--applies-to",
        action="append",
        default=None,
        metavar="BRANCH",
        help="Target branch; repeat for multiple branches",
    )
    p_gh_issues.add_argument(
        "--status-map",
        action="append",
        default=[],
        metavar="SOURCE=TARGET",
        help="Map GitHub states to project statuses, e.g. closed=done",
    )
    p_gh_issues.add_argument(
        "--state",
        choices=["open", "closed", "all"],
        default="open",
        help="GitHub issue state to fetch",
    )
    p_gh_issues.add_argument(
        "--label",
        action="append",
        default=[],
        help="Only fetch GitHub issues with this label; repeat for multiple labels",
    )
    p_gh_issues.add_argument(
        "--since",
        default=None,
        help="Only fetch issues updated after this ISO-8601 timestamp",
    )
    p_gh_issues.add_argument("--limit", type=int, default=50, help="Maximum issues to import")
    p_gh_issues.add_argument(
        "--include-pulls",
        action="store_true",
        help="Also import pull requests returned by GitHub's issues endpoint",
    )
    p_gh_issues.add_argument(
        "--github-token",
        default=None,
        help="GitHub token; defaults to GITHUB_TOKEN or GH_TOKEN",
    )
    p_gh_issues.add_argument("--dry-run", action="store_true", help="Print the import summary only")

    p_md = sub.add_parser(
        "import-markdown-list",
        help="Create items from GitHub-style Markdown task lists",
    )
    p_md.add_argument("source", help="Markdown file or directory containing *.md files")
    p_md.add_argument("--config", default="server.toml")
    p_md.add_argument("--project-key", required=True)
    p_md.add_argument(
        "--kind",
        default=None,
        help="IssueDeck kind to create; defaults to the first kind in the project config",
    )
    p_md.add_argument("--tag", action="append", default=[], help="Add a tag")
    p_md.add_argument(
        "--applies-to",
        action="append",
        default=None,
        metavar="BRANCH",
        help="Target branch; repeat for multiple branches",
    )
    p_md.add_argument(
        "--include-checked",
        action="store_true",
        help="Import checked tasks into the first terminal project status",
    )
    p_md.add_argument("--dry-run", action="store_true", help="Print the import summary only")

    p_csv = sub.add_parser(
        "import-csv",
        help="Create items from CSV tracker exports",
    )
    p_csv.add_argument("source", help="CSV file exported from a tracker or spreadsheet")
    p_csv.add_argument("--config", default="server.toml")
    p_csv.add_argument("--project-key", required=True)
    p_csv.add_argument(
        "--kind",
        default=None,
        help="Default IssueDeck kind; row kind/type columns can override it",
    )
    p_csv.add_argument(
        "--default-status",
        default=None,
        help="Status to use when a row has no status; defaults to the first non-terminal status",
    )
    p_csv.add_argument("--tag", action="append", default=[], help="Add a tag")
    p_csv.add_argument(
        "--applies-to",
        action="append",
        default=None,
        metavar="BRANCH",
        help="Default target branch; repeat for multiple branches",
    )
    p_csv.add_argument(
        "--preset",
        action="append",
        default=[],
        choices=["generic", "github", "jira", "linear"],
        help="Apply common CSV column aliases",
    )
    p_csv.add_argument(
        "--field-alias",
        action="append",
        default=[],
        metavar="FIELD=ALIAS[,ALIAS...]",
        help="Add CSV column aliases, e.g. title=Issue, custom.priority=Priority",
    )
    p_csv.add_argument(
        "--status-map",
        action="append",
        default=[],
        metavar="SOURCE=TARGET",
        help="Map source statuses to project statuses, e.g. Closed=done",
    )
    p_csv.add_argument("--dry-run", action="store_true", help="Print the import summary only")

    p_json = sub.add_parser(
        "import-json",
        help="Create items from JSON tracker exports",
    )
    p_json.add_argument("source", help="JSON file exported from a tracker")
    p_json.add_argument("--config", default="server.toml")
    p_json.add_argument("--project-key", required=True)
    p_json.add_argument(
        "--kind",
        default=None,
        help="Default IssueDeck kind; row kind/type fields can override it",
    )
    p_json.add_argument(
        "--default-status",
        default=None,
        help=(
            "Status to use when an object has no status; "
            "defaults to the first non-terminal status"
        ),
    )
    p_json.add_argument("--tag", action="append", default=[], help="Add a tag")
    p_json.add_argument(
        "--applies-to",
        action="append",
        default=None,
        metavar="BRANCH",
        help="Default target branch; repeat for multiple branches",
    )
    p_json.add_argument(
        "--preset",
        action="append",
        default=[],
        choices=["generic", "github", "jira", "linear"],
        help="Apply common JSON field aliases",
    )
    p_json.add_argument(
        "--field-alias",
        action="append",
        default=[],
        metavar="FIELD=ALIAS[,ALIAS...]",
        help="Add JSON field aliases, e.g. title=Issue, custom.priority=priority",
    )
    p_json.add_argument(
        "--status-map",
        action="append",
        default=[],
        metavar="SOURCE=TARGET",
        help="Map source statuses to project statuses, e.g. Closed=done",
    )
    p_json.add_argument("--dry-run", action="store_true", help="Print the import summary only")

    sub.add_parser("mcp", help="Run the MCP stdio server")

    args = parser.parse_args(argv)

    if args.cmd == "demo":
        return _cmd_demo(
            Path(args.config),
            args.project_key,
            host=args.host,
            port=args.port,
            force_reset_demo_data=args.force_reset_demo_data,
            open_browser=args.open,
        )
    if args.cmd == "serve":
        return _cmd_serve(Path(args.config), host=args.host, port=args.port)
    if args.cmd == "migrate":
        return asyncio.run(_cmd_migrate(
            Path(args.config), Path(args.from_frontmatter),
            args.project_key, args.dry_run, args.force_reset,
            args.field_alias, args.preset,
        ))
    if args.cmd == "export":
        return asyncio.run(_cmd_export(
            Path(args.config), args.project_key, Path(args.out),
        ))
    if args.cmd == "export-audit-bundle":
        return asyncio.run(_cmd_export_audit_bundle(
            Path(args.config), args.project_key, Path(args.out),
        ))
    if args.cmd == "seed-demo":
        return asyncio.run(_cmd_seed_demo(
            Path(args.config), args.project_key, args.force_reset,
        ))
    if args.cmd == "create-item":
        return asyncio.run(_cmd_create_item(
            Path(args.config),
            args.project_key,
            kind=args.kind,
            title=args.title,
            body=args.body,
            body_file=_path_or_stdin(args.body_file),
            tags=args.tag,
            applies_to=args.applies_to,
            custom_field_options=args.custom_field,
            external_link_options=args.external_link,
            dry_run=args.dry_run,
            output_format=args.format,
        ))
    if args.cmd == "update-item":
        return asyncio.run(_cmd_update_item(
            Path(args.config),
            args.project_key,
            args.local_id,
            title=args.title,
            status=args.status,
            body=args.body,
            body_file=_path_or_stdin(args.body_file),
            append_body=args.append_body,
            append_body_file=_path_or_stdin(args.append_body_file),
            tags=args.tag,
            applies_to=args.applies_to,
            custom_field_options=args.custom_field,
            external_link_options=args.external_link,
            clear_external_links=args.clear_external_links,
            dry_run=args.dry_run,
            output_format=args.format,
        ))
    if args.cmd == "bulk-update-items":
        return asyncio.run(_cmd_bulk_update_items(
            Path(args.config),
            args.project_key,
            args.local_ids,
            action=args.action,
            kind=args.kind,
            status=args.status,
            tags=args.tag,
            tag_mode=args.tag_mode,
            applies_to=args.applies_to,
            custom_field_options=args.custom_field,
            reason=args.reason,
            dry_run=args.dry_run,
            output_format=args.format,
        ))
    if args.cmd == "ship-item":
        return asyncio.run(_cmd_ship_item(
            Path(args.config),
            args.project_key,
            args.local_id,
            branch=args.branch,
            version=args.version,
            commits=args.commit,
            dry_run=args.dry_run,
            output_format=args.format,
        ))
    if args.cmd == "append-item-event":
        return asyncio.run(_cmd_append_item_event(
            Path(args.config),
            args.project_key,
            args.local_id,
            body=args.body,
            body_file=_path_or_stdin(args.body_file),
            event_type=args.event_type,
            actor_type=args.actor_type,
            actor_name=args.actor_name,
            metadata_options=args.metadata,
            dry_run=args.dry_run,
            output_format=args.format,
        ))
    if args.cmd == "list-items":
        return asyncio.run(_cmd_list_items(
            Path(args.config),
            args.project_key,
            kinds=args.kind,
            statuses=args.status,
            tags=args.tag,
            applies_to=args.applies_to,
            relation_types=args.relation_type,
            custom_field_options=args.custom_field,
            include_deleted=args.include_deleted,
            only_deleted=args.only_deleted,
            limit=args.limit,
            output_format=args.format,
        ))
    if args.cmd == "get-item":
        return asyncio.run(_cmd_get_item(
            Path(args.config),
            args.project_key,
            args.local_id,
            include_deleted=args.include_deleted,
            output_format=args.format,
        ))
    if args.cmd == "import-github-url":
        return asyncio.run(_cmd_import_github_url(
            Path(args.config),
            args.project_key,
            args.url,
            kind=args.kind,
            title=args.title,
            body=args.body,
            tags=args.tag,
            applies_to=args.applies_to,
            link_label=args.link_label,
            dry_run=args.dry_run,
        ))
    if args.cmd == "import-github-issues":
        return asyncio.run(_cmd_import_github_issues(
            Path(args.config),
            args.project_key,
            args.repo,
            kind=args.kind,
            default_status=args.default_status,
            tags=args.tag,
            applies_to=args.applies_to,
            status_maps=args.status_map,
            state=args.state,
            labels=args.label,
            since=args.since,
            limit=args.limit,
            include_pulls=args.include_pulls,
            github_token=args.github_token,
            dry_run=args.dry_run,
        ))
    if args.cmd == "import-markdown-list":
        return asyncio.run(_cmd_import_markdown_list(
            Path(args.config),
            args.project_key,
            Path(args.source),
            kind=args.kind,
            tags=args.tag,
            applies_to=args.applies_to,
            include_checked=args.include_checked,
            dry_run=args.dry_run,
        ))
    if args.cmd == "import-csv":
        return asyncio.run(_cmd_import_csv(
            Path(args.config),
            args.project_key,
            Path(args.source),
            kind=args.kind,
            default_status=args.default_status,
            tags=args.tag,
            applies_to=args.applies_to,
            presets=args.preset,
            field_aliases=args.field_alias,
            status_maps=args.status_map,
            dry_run=args.dry_run,
        ))
    if args.cmd == "import-json":
        return asyncio.run(_cmd_import_json(
            Path(args.config),
            args.project_key,
            Path(args.source),
            kind=args.kind,
            default_status=args.default_status,
            tags=args.tag,
            applies_to=args.applies_to,
            presets=args.preset,
            field_aliases=args.field_alias,
            status_maps=args.status_map,
            dry_run=args.dry_run,
        ))
    if args.cmd == "mcp":
        from issuedeck.mcp.__main__ import run as mcp_run
        return mcp_run()

    parser.print_help()
    return 0


def _cmd_demo(
    config_path: Path,
    project_key: str,
    *,
    host: str | None,
    port: int | None,
    force_reset_demo_data: bool,
    open_browser: bool,
    serve: bool = True,
) -> int:
    from issuedeck.core.config import load_server_config

    config_created = _ensure_demo_config(config_path)
    server_cfg = load_server_config(config_path)
    project_created = _ensure_demo_project_config(server_cfg.projects_dir, project_key)

    db_path = _upgrade_database(config_path)
    seed_state = "skipped"
    try:
        asyncio.run(_cmd_seed_demo(config_path, project_key, force_reset_demo_data))
        seed_state = "seeded"
    except ValueError as exc:
        if "already has" not in str(exc):
            raise
        print(f"[skip] demo data already exists: {exc}", file=sys.stderr)

    registry = _build_registry(config_path)
    cfg = registry.server
    url = _dashboard_url(cfg.host, cfg.port, project_key, host=host, port=port)

    print(f"[ok] config: {config_path} ({'created' if config_created else 'existing'})",
          file=sys.stderr)
    if project_created:
        print(f"[ok] project config: {cfg.projects_dir / f'{project_key}.toml'}",
              file=sys.stderr)
    print(f"[ok] database migrated: {db_path}", file=sys.stderr)
    print(f"[ok] demo data: {seed_state}", file=sys.stderr)
    print(f"[ok] dashboard: {url}", file=sys.stderr)
    print(f"[ok] login token: {_demo_token_hint(config_created)}", file=sys.stderr)

    if open_browser:
        import webbrowser
        webbrowser.open(url)

    if not serve:
        return 0
    return _cmd_serve(config_path, host=host, port=port)


def _cmd_serve(config_path: Path, *, host: str | None, port: int | None) -> int:
    import uvicorn

    from issuedeck.app import create_app
    _upgrade_database(config_path)
    app = create_app(config_path)
    cfg = app.state.registry.server
    uvicorn.run(app, host=host or cfg.host, port=port or cfg.port,
                log_level=cfg.log_level)
    return 0


def _build_registry(config_path: Path):
    from issuedeck.core.config import (
        ConfigRegistry,
        load_project_config,
        load_server_config,
    )
    from issuedeck.core.errors import ConfigError

    server_cfg = load_server_config(config_path)
    projects: dict = {}
    if server_cfg.projects_dir.exists():
        for f in sorted(server_cfg.projects_dir.glob("*.toml")):
            pc = load_project_config(f)
            if pc.key != f.stem:
                raise ConfigError(
                    f"{f}: key '{pc.key}' must equal filename stem '{f.stem}'"
                )
            if pc.key in projects:
                raise ConfigError(f"duplicate project key '{pc.key}'")
            projects[pc.key] = pc
    return ConfigRegistry(server=server_cfg, projects=projects)


def _ensure_demo_config(config_path: Path) -> bool:
    if config_path.exists():
        return False

    config_path.parent.mkdir(parents=True, exist_ok=True)
    data_dir, projects_dir = _demo_config_paths(config_path)
    config_path.write_text(
        "\n".join([
            'host = "127.0.0.1"',
            "port = 8765",
            f'api_token = "{_DEMO_TOKEN}"',
            f'data_dir = "{data_dir}"',
            f'projects_dir = "{projects_dir}"',
            'log_level = "info"',
            "",
            "[sqlite]",
            "wal_mode = true",
            "busy_timeout_ms = 5000",
            "",
        ]),
        encoding="utf-8",
    )
    return True


def _demo_config_paths(config_path: Path) -> tuple[str, str]:
    config_dir = config_path.parent if config_path.parent != Path("") else Path(".")
    if config_dir.resolve() == Path.cwd().resolve():
        return "./data", "./projects"
    return (
        (config_dir / "data").resolve().as_posix(),
        (config_dir / "projects").resolve().as_posix(),
    )


def _ensure_demo_project_config(projects_dir: Path, project_key: str) -> bool:
    if project_key != "example":
        return False
    project_path = projects_dir / "example.toml"
    if project_path.exists():
        return False
    projects_dir.mkdir(parents=True, exist_ok=True)
    project_path.write_text(_DEMO_PROJECT_TOML, encoding="utf-8")
    return True


def _upgrade_database(config_path: Path) -> Path:
    from alembic import command
    from alembic.config import Config as AlembicConfig

    from issuedeck.core.config import load_server_config

    server_cfg = load_server_config(config_path)
    db_path = server_cfg.data_dir / "tracker.db"
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    alembic_cfg = AlembicConfig()
    alembic_cfg.set_main_option("script_location", migrations_dir.as_posix())
    alembic_cfg.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{db_path.resolve().as_posix()}",
    )
    command.upgrade(alembic_cfg, "head")
    return db_path


def _dashboard_url(
    configured_host: str,
    configured_port: int,
    project_key: str,
    *,
    host: str | None,
    port: int | None,
) -> str:
    display_host = host or configured_host
    if display_host in {"0.0.0.0", "::"}:
        display_host = "127.0.0.1"
    return f"http://{display_host}:{port or configured_port}/dashboard/{project_key}"


def _demo_token_hint(config_created: bool) -> str:
    if os.environ.get("ISSUEDECK_API_TOKEN"):
        return "ISSUEDECK_API_TOKEN from your environment"
    if config_created:
        return _DEMO_TOKEN
    return "api_token from your config file"


def _format_custom_fields(values: dict[str, object]) -> str:
    parts = [
        f"{key}={value}"
        for key, value in sorted(values.items())
        if value is not None and value != ""
    ]
    return ", ".join(parts)


def _parse_key_value_options(options: list[str] | None, label: str) -> dict[str, object]:
    values: dict[str, object] = {}
    for option in options or []:
        if "=" not in option:
            raise ValueError(f"invalid {label} '{option}'; expected FIELD=VALUE")
        key, value = option.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid {label} '{option}'; expected FIELD=VALUE")
        values[key] = value.strip()
    return values


def _path_or_stdin(value: str | None) -> Path | str | None:
    if value and value != "-":
        return Path(value)
    return value


def _parse_custom_field_assignments(
    project,
    options: list[str] | None,
    *,
    require_required: bool,
) -> dict[str, object]:
    from issuedeck.core.errors import InvalidCustomField
    from issuedeck.features.items.custom_fields import (
        normalize_custom_field_value,
        normalize_custom_fields,
    )

    raw_values = _parse_key_value_options(options, "custom field")
    if require_required:
        return normalize_custom_fields(project, raw_values)

    unknown = sorted(set(raw_values) - set(project.custom_fields))
    if unknown:
        raise InvalidCustomField(
            f"unknown custom field(s): {', '.join(unknown)}",
            details={"project_key": project.key, "fields": unknown},
        )

    normalized: dict[str, object] = {}
    for key, value in raw_values.items():
        normalized[key] = normalize_custom_field_value(
            project.key,
            key,
            project.custom_fields[key],
            value,
        )
    return normalized


def _parse_external_link_options(options: list[str] | None) -> list[dict[str, str | None]]:
    links: list[dict[str, str | None]] = []
    for option in options or []:
        raw = option.strip()
        if not raw:
            continue
        label: str | None = None
        url = raw
        if "|" in raw:
            label_part, url_part = raw.split("|", 1)
            label = label_part.strip() or None
            url = url_part.strip()
        if not url:
            raise ValueError(f"invalid external link '{option}'; expected URL or 'Label | URL'")
        links.append({"url": url, "label": label})
    return links


def _read_body_value(body: str | None, body_file: Path | str | None) -> str:
    return _read_optional_text_value(body, body_file, "body") or ""


def _read_optional_text_value(
    value: str | None,
    file_value: Path | str | None,
    label: str,
) -> str | None:
    if file_value is None:
        return value
    if value is not None:
        raise ValueError(f"{label} and {label}_file are mutually exclusive")
    if file_value == "-":
        return sys.stdin.read()
    return Path(file_value).read_text(encoding="utf-8")


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [
        max(len(header), *(len(str(row[index])) for row in rows))
        for index, header in enumerate(headers)
    ]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))


async def _cmd_migrate(
    config_path: Path, source_dir: Path, project_key: str,
    dry_run: bool, force_reset: bool, field_aliases: list[str], presets: list[str],
) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.migrate.frontmatter import (
        FrontmatterMapping,
        migrate_frontmatter_bundle,
    )

    registry = _build_registry(config_path)
    mapping = FrontmatterMapping.from_alias_options(field_aliases, presets=presets)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            report = await migrate_frontmatter_bundle(
                source_dir=source_dir, project_key=project_key,
                registry=registry, db=session,
                dry_run=dry_run, force_reset=force_reset,
                mapping=mapping,
            )
            print(
                f"[{'dry-run' if dry_run else 'ok'}] planned={report.items_planned} "
                f"written={report.items_written} "
                f"ship_records={report.ship_records} "
                f"ship_commits={report.ship_commits} "
                f"external_links={report.external_links}",
                file=sys.stderr,
            )
    finally:
        await engine.dispose()
    return 0


async def _cmd_export(config_path: Path, project_key: str, out_dir: Path) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.export.md_bundle import export_md_bundle

    registry = _build_registry(config_path)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            report = await export_md_bundle(
                session=session, registry=registry,
                project_key=project_key, out_dir=out_dir,
            )
            print(f"[ok] wrote {report.items_written} items to {out_dir}",
                  file=sys.stderr)
    finally:
        await engine.dispose()
    return 0


async def _cmd_export_audit_bundle(
    config_path: Path,
    project_key: str,
    out_path: Path,
) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.export.md_bundle import export_audit_bundle

    registry = _build_registry(config_path)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            report = await export_audit_bundle(
                session=session,
                registry=registry,
                project_key=project_key,
                out_path=out_path,
            )
            print(
                "[ok] wrote audit bundle to "
                f"{report.bundle_path} "
                f"(items={report.items_written}, "
                f"relationships={report.relationships_written}, "
                f"work_sessions={report.work_sessions_written}, "
                f"import_batches={report.import_batches_written})",
                file=sys.stderr,
            )
    finally:
        await engine.dispose()
    return 0


async def _cmd_seed_demo(
    config_path: Path, project_key: str, force_reset: bool,
) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.demo.seed import seed_demo_project

    _upgrade_database(config_path)
    registry = _build_registry(config_path)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            report = await seed_demo_project(
                session=session,
                registry=registry,
                project_key=project_key,
                force_reset=force_reset,
            )
            print(
                f"[ok] seeded {report.items_written} demo items "
                f"for project '{report.project_key}'",
                file=sys.stderr,
            )
    finally:
        await engine.dispose()
    return 0


async def _cmd_create_item(
    config_path: Path,
    project_key: str,
    *,
    kind: str | None,
    title: str,
    body: str | None,
    body_file: Path | str | None,
    tags: list[str],
    applies_to: list[str] | None,
    custom_field_options: list[str],
    external_link_options: list[str],
    dry_run: bool,
    output_format: str,
) -> int:
    from pydantic import ValidationError

    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.core.errors import IssueDeckError
    from issuedeck.features.items.repo import ItemRepo
    from issuedeck.features.items.schemas import CreateItemRequest
    from issuedeck.features.items.service import ItemService

    try:
        registry = _build_registry(config_path)
        project = registry.project(project_key)
        item_kind = kind or next(iter(project.kinds.keys()))
        registry.validate_kind(project_key, item_kind)
        if applies_to is not None:
            for branch in applies_to:
                registry.validate_branch(project_key, branch)
        body_value = _read_body_value(body, body_file)
        custom_fields = _parse_custom_field_assignments(
            project,
            custom_field_options,
            require_required=True,
        )
        external_links = _parse_external_link_options(external_link_options)
        req = CreateItemRequest(
            kind=item_kind,
            title=title,
            body=body_value,
            tags=tags,
            applies_to=applies_to,
            custom_fields=custom_fields,
            external_links=external_links,
        )
    except (ValidationError, ValueError, IssueDeckError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if dry_run:
        print(req.model_dump_json(indent=2))
        return 0

    _upgrade_database(config_path)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            service = ItemService(ItemRepo(session), registry, session)
            item = await service.create(project_key, req)
    except IssueDeckError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    finally:
        await engine.dispose()

    payload = item.model_dump(mode="json")
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(item.local_id)
    print(f"[ok] created {item.local_id}", file=sys.stderr)
    return 0


async def _cmd_update_item(
    config_path: Path,
    project_key: str,
    local_id: str,
    *,
    title: str | None,
    status: str | None,
    body: str | None,
    body_file: Path | str | None,
    append_body: str | None,
    append_body_file: Path | str | None,
    tags: list[str] | None,
    applies_to: list[str] | None,
    custom_field_options: list[str],
    external_link_options: list[str] | None,
    clear_external_links: bool,
    dry_run: bool,
    output_format: str,
) -> int:
    from pydantic import ValidationError

    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.core.errors import IssueDeckError
    from issuedeck.features.items.repo import ItemRepo
    from issuedeck.features.items.schemas import UpdateItemRequest
    from issuedeck.features.items.service import ItemService

    try:
        registry = _build_registry(config_path)
        project = registry.project(project_key)
        if status is not None:
            registry.validate_status(project_key, status)
        if applies_to is not None:
            for branch in applies_to:
                registry.validate_branch(project_key, branch)
        body_value = _read_optional_text_value(body, body_file, "body")
        append_body_value = _read_optional_text_value(
            append_body,
            append_body_file,
            "append_body",
        )
        custom_fields = (
            _parse_custom_field_assignments(
                project,
                custom_field_options,
                require_required=False,
            )
            if custom_field_options
            else None
        )
        if clear_external_links and external_link_options:
            raise ValueError("clear_external_links cannot be combined with external_link")
        external_links = None
        if clear_external_links:
            external_links = []
        elif external_link_options is not None:
            external_links = _parse_external_link_options(external_link_options)

        if not any(
            value is not None
            for value in (
                title,
                status,
                body_value,
                append_body_value,
                tags,
                applies_to,
                custom_fields,
                external_links,
            )
        ):
            raise ValueError("update requires at least one field to change")

        req = UpdateItemRequest(
            title=title,
            status=status,
            body=body_value,
            append_body=append_body_value,
            tags=tags,
            applies_to=applies_to,
            custom_fields=custom_fields,
            external_links=external_links,
        )
    except (ValidationError, ValueError, IssueDeckError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if dry_run:
        print(req.model_dump_json(indent=2, exclude_none=True))
        return 0

    _upgrade_database(config_path)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            service = ItemService(ItemRepo(session), registry, session)
            item = await service.update(project_key, local_id, req)
    except IssueDeckError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    finally:
        await engine.dispose()

    payload = item.model_dump(mode="json")
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(item.local_id)
    print(f"[ok] updated {item.local_id}", file=sys.stderr)
    return 0


async def _cmd_bulk_update_items(
    config_path: Path,
    project_key: str,
    local_ids: list[str],
    *,
    action: str,
    kind: str | None,
    status: str | None,
    tags: list[str] | None,
    tag_mode: str,
    applies_to: list[str] | None,
    custom_field_options: list[str],
    reason: str,
    dry_run: bool,
    output_format: str,
) -> int:
    from pydantic import ValidationError

    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.core.errors import IssueDeckError
    from issuedeck.features.items.repo import ItemRepo
    from issuedeck.features.items.schemas import BulkUpdateItemsRequest
    from issuedeck.features.items.service import ItemService

    try:
        registry = _build_registry(config_path)
        project = registry.project(project_key)
        if kind is not None:
            registry.validate_kind(project_key, kind)
        if status is not None:
            registry.validate_status(project_key, status)
        if applies_to is not None:
            for branch in applies_to:
                registry.validate_branch(project_key, branch)
        custom_fields = (
            _parse_custom_field_assignments(
                project,
                custom_field_options,
                require_required=False,
            )
            if custom_field_options
            else None
        )
        req = BulkUpdateItemsRequest(
            local_ids=local_ids,
            action=action,
            kind=kind,
            status=status,
            tags=tags,
            tag_mode=tag_mode,
            applies_to=applies_to,
            custom_fields=custom_fields,
            reason=reason,
        )
    except (ValidationError, ValueError, IssueDeckError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if dry_run:
        print(req.model_dump_json(indent=2, exclude_none=True))
        return 0

    _upgrade_database(config_path)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            service = ItemService(ItemRepo(session), registry, session)
            result = await service.bulk_update(project_key, req)
    except IssueDeckError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    finally:
        await engine.dispose()

    payload = result.model_dump(mode="json")
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(
        f"[ok] {result.action} updated={result.updated_count} "
        f"requested={result.requested_count}",
        file=sys.stderr,
    )
    for item in result.items:
        print(item.local_id)
    return 0


async def _cmd_ship_item(
    config_path: Path,
    project_key: str,
    local_id: str,
    *,
    branch: str,
    version: str,
    commits: list[str],
    dry_run: bool,
    output_format: str,
) -> int:
    from pydantic import ValidationError

    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.core.errors import IssueDeckError
    from issuedeck.features.items.repo import ItemRepo
    from issuedeck.features.items.schemas import ShipItemRequest
    from issuedeck.features.items.service import ItemService

    try:
        registry = _build_registry(config_path)
        registry.project(project_key)
        registry.validate_branch(project_key, branch)
        req = ShipItemRequest(branch=branch, version=version, commits=commits)
    except (ValidationError, ValueError, IssueDeckError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if dry_run:
        print(req.model_dump_json(indent=2))
        return 0

    _upgrade_database(config_path)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            service = ItemService(ItemRepo(session), registry, session)
            item = await service.ship(project_key, local_id, req)
    except IssueDeckError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    finally:
        await engine.dispose()

    payload = item.model_dump(mode="json")
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(item.local_id)
    print(f"[ok] shipped {item.local_id} to {branch} as {version}", file=sys.stderr)
    return 0


async def _cmd_append_item_event(
    config_path: Path,
    project_key: str,
    local_id: str,
    *,
    body: str | None,
    body_file: Path | str | None,
    event_type: str,
    actor_type: str,
    actor_name: str,
    metadata_options: list[str],
    dry_run: bool,
    output_format: str,
) -> int:
    from pydantic import ValidationError

    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.core.errors import IssueDeckError
    from issuedeck.features.items.repo import ItemRepo
    from issuedeck.features.items.schemas import CreateItemEventRequest
    from issuedeck.features.items.service import ItemService

    try:
        registry = _build_registry(config_path)
        registry.project(project_key)
        body_value = _read_body_value(body, body_file)
        metadata = _parse_key_value_options(metadata_options, "metadata")
        req = CreateItemEventRequest(
            event_type=event_type,
            actor_type=actor_type,
            actor_name=actor_name,
            body=body_value,
            metadata=metadata,
        )
    except (ValidationError, ValueError, IssueDeckError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if dry_run:
        print(req.model_dump_json(indent=2))
        return 0

    _upgrade_database(config_path)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            service = ItemService(ItemRepo(session), registry, session)
            event = await service.add_event(project_key, local_id, req)
    except IssueDeckError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    finally:
        await engine.dispose()

    payload = event.model_dump(mode="json")
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(event.id)
    print(f"[ok] appended {event.event_type} event to {local_id}", file=sys.stderr)
    return 0


async def _cmd_list_items(
    config_path: Path,
    project_key: str,
    *,
    kinds: list[str],
    statuses: list[str],
    tags: list[str],
    applies_to: list[str],
    relation_types: list[str],
    custom_field_options: list[str],
    include_deleted: bool,
    only_deleted: bool,
    limit: int,
    output_format: str,
) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.items.custom_fields import parse_custom_field_filter_options
    from issuedeck.features.items.repo import ItemRepo
    from issuedeck.features.items.service import ItemService

    _upgrade_database(config_path)
    registry = _build_registry(config_path)
    project = registry.project(project_key)
    custom_fields = parse_custom_field_filter_options(project, custom_field_options)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            service = ItemService(ItemRepo(session), registry, session)
            result = await service.list_items(
                project_key,
                kinds=kinds or None,
                statuses=statuses or None,
                tags=tags or None,
                applies_to=applies_to or None,
                relationship_types=relation_types or None,
                custom_fields=custom_fields or None,
                include_deleted=include_deleted,
                only_deleted=only_deleted,
                limit=limit,
            )
    finally:
        await engine.dispose()

    payload = [item.model_dump(mode="json") for item in result.items]
    if output_format == "json":
        print(json.dumps({
            "items": payload,
            "next_cursor": result.next_cursor,
            "limit": result.limit,
        }, ensure_ascii=False, indent=2))
        return 0

    if not result.items:
        print("No matching items.", file=sys.stderr)
        return 0

    rows = [
        [
            item.local_id,
            item.kind,
            item.status,
            item.title,
            ", ".join(item.tags),
            _format_custom_fields(item.custom_fields),
        ]
        for item in result.items
    ]
    _print_table(["ID", "Kind", "Status", "Title", "Tags", "Custom fields"], rows)
    if result.next_cursor:
        print(
            f"[more] increase --limit or use the dashboard/API cursor: {result.next_cursor}",
            file=sys.stderr,
        )
    return 0


async def _cmd_get_item(
    config_path: Path,
    project_key: str,
    local_id: str,
    *,
    include_deleted: bool,
    output_format: str,
) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.items.repo import ItemRepo
    from issuedeck.features.items.service import ItemService

    _upgrade_database(config_path)
    registry = _build_registry(config_path)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            service = ItemService(ItemRepo(session), registry, session)
            item = await service.get(
                project_key,
                local_id,
                include_deleted=include_deleted,
            )
    finally:
        await engine.dispose()

    payload = item.model_dump(mode="json")
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"{item.local_id}  {item.kind}  {item.status}")
    print(item.title)
    if item.deleted_at:
        print(f"Deleted: {item.deleted_at}")
    if item.tags:
        print(f"Tags: {', '.join(item.tags)}")
    if item.applies_to:
        print(f"Applies to: {', '.join(item.applies_to)}")
    custom_fields = _format_custom_fields(item.custom_fields)
    if custom_fields:
        print(f"Custom fields: {custom_fields}")
    if item.external_links:
        print("External links:")
        for link in item.external_links:
            label = f"{link.label}: " if link.label else ""
            print(f"- {label}{link.url}")
    if item.ship_records:
        print("Ship records:")
        for record in item.ship_records:
            print(f"- {record.branch_key} {record.version} ({record.shipped_at})")
    if item.relationships:
        print("Relationships:")
        for rel in item.relationships:
            print(f"- {rel.relation_type}: {rel.to_local_id}")
    if item.body:
        print("")
        print(item.body)
    return 0


async def _cmd_import_github_url(
    config_path: Path,
    project_key: str,
    url: str,
    *,
    kind: str | None,
    title: str | None,
    body: str | None,
    tags: list[str],
    applies_to: list[str] | None,
    link_label: str | None,
    dry_run: bool,
) -> int:
    from pydantic import ValidationError

    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.items.external_links import github_import_payload
    from issuedeck.features.items.repo import ItemRepo
    from issuedeck.features.items.schemas import CreateItemRequest
    from issuedeck.features.items.service import ItemService

    registry = _build_registry(config_path)
    project = registry.project(project_key)
    item_kind = kind or next(iter(project.kinds.keys()))
    try:
        payload = github_import_payload(
            url,
            kind=item_kind,
            title=title,
            body=body,
            tags=tags or None,
            applies_to=applies_to,
            link_label=link_label,
        )
        req = CreateItemRequest.model_validate(payload)
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if dry_run:
        print(req.model_dump_json(indent=2))
        return 0

    _upgrade_database(config_path)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            service = ItemService(ItemRepo(session), registry, session)
            item = await service.create(project_key, req)
            print(
                f"[ok] created {item.local_id} from {req.external_links[0].url}",
                file=sys.stderr,
            )
            print(item.local_id)
    finally:
        await engine.dispose()
    return 0


async def _cmd_import_github_issues(
    config_path: Path,
    project_key: str,
    repo_value: str,
    *,
    kind: str | None,
    default_status: str | None,
    tags: list[str],
    applies_to: list[str] | None,
    status_maps: list[str],
    state: str,
    labels: list[str],
    since: str | None,
    limit: int,
    include_pulls: bool,
    github_token: str | None,
    dry_run: bool,
) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.migrate.csv_items import parse_status_map_options
    from issuedeck.features.migrate.github_issues import (
        fetch_github_issue_rows,
        import_github_issue_rows,
        parse_github_repo,
    )

    try:
        repo_ref = parse_github_repo(repo_value)
        status_map = parse_status_map_options(status_maps)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    _upgrade_database(config_path)
    registry = _build_registry(config_path)
    project = registry.project(project_key)
    item_kind = kind or next(iter(project.kinds.keys()))
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        rows, fetch_report = await fetch_github_issue_rows(
            repo_ref,
            token=github_token,
            state=state,
            labels=labels,
            since=since,
            limit=limit,
            include_pulls=include_pulls,
        )
        async with session_factory() as session:
            report = await import_github_issue_rows(
                rows,
                project_key,
                registry,
                session,
                kind=item_kind,
                default_status=default_status,
                tags=tags or None,
                applies_to=applies_to,
                status_map=status_map,
                dry_run=dry_run,
            )
            report.issues_fetched = fetch_report.issues_fetched
            report.pulls_skipped = fetch_report.pulls_skipped
            label = "dry-run" if dry_run else "ok"
            print(
                f"[{label}] repo={repo_ref.owner}/{repo_ref.repo} "
                f"fetched={report.issues_fetched} "
                f"pulls_skipped={report.pulls_skipped} "
                f"existing_skipped={report.existing_skipped} "
                f"planned={report.items_planned} "
                f"written={report.items_written} "
                f"status_mapped={report.status_mapped} "
                f"external_links={report.external_links}",
                file=sys.stderr,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        await engine.dispose()
    return 0


async def _cmd_import_markdown_list(
    config_path: Path,
    project_key: str,
    source: Path,
    *,
    kind: str | None,
    tags: list[str],
    applies_to: list[str] | None,
    include_checked: bool,
    dry_run: bool,
) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.migrate.markdown_tasks import import_markdown_task_list

    _upgrade_database(config_path)
    registry = _build_registry(config_path)
    project = registry.project(project_key)
    item_kind = kind or next(iter(project.kinds.keys()))
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            report = await import_markdown_task_list(
                source,
                project_key,
                registry,
                session,
                kind=item_kind,
                tags=tags or None,
                applies_to=applies_to,
                include_checked=include_checked,
                dry_run=dry_run,
            )
            label = "dry-run" if dry_run else "ok"
            print(
                f"[{label}] tasks={report.tasks_found} "
                f"planned={report.items_planned} "
                f"written={report.items_written} "
                f"checked={report.checked_tasks} "
                f"skipped_checked={report.skipped_checked} "
                f"external_links={report.external_links}",
                file=sys.stderr,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        await engine.dispose()
    return 0


async def _cmd_import_csv(
    config_path: Path,
    project_key: str,
    source: Path,
    *,
    kind: str | None,
    default_status: str | None,
    tags: list[str],
    applies_to: list[str] | None,
    presets: list[str],
    field_aliases: list[str],
    status_maps: list[str],
    dry_run: bool,
) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.migrate.csv_items import (
        CsvItemMapping,
        import_csv_items,
        parse_status_map_options,
    )

    try:
        mapping = CsvItemMapping.from_alias_options(field_aliases, presets=presets)
        status_map = parse_status_map_options(status_maps)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    _upgrade_database(config_path)
    registry = _build_registry(config_path)
    project = registry.project(project_key)
    item_kind = kind or next(iter(project.kinds.keys()))
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            report = await import_csv_items(
                source,
                project_key,
                registry,
                session,
                kind=item_kind,
                default_status=default_status,
                tags=tags or None,
                applies_to=applies_to,
                status_map=status_map,
                mapping=mapping,
                dry_run=dry_run,
            )
            label = "dry-run" if dry_run else "ok"
            print(
                f"[{label}] rows={report.rows_found} "
                f"skipped={report.rows_skipped} "
                f"planned={report.items_planned} "
                f"written={report.items_written} "
                f"status_mapped={report.status_mapped} "
                f"custom_fields={report.custom_fields} "
                f"external_links={report.external_links}",
                file=sys.stderr,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        await engine.dispose()
    return 0


async def _cmd_import_json(
    config_path: Path,
    project_key: str,
    source: Path,
    *,
    kind: str | None,
    default_status: str | None,
    tags: list[str],
    applies_to: list[str] | None,
    presets: list[str],
    field_aliases: list[str],
    status_maps: list[str],
    dry_run: bool,
) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.migrate.csv_items import parse_status_map_options
    from issuedeck.features.migrate.json_items import (
        JsonItemMapping,
        import_json_items,
    )

    try:
        mapping = JsonItemMapping.from_alias_options(field_aliases, presets=presets)
        status_map = parse_status_map_options(status_maps)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    _upgrade_database(config_path)
    registry = _build_registry(config_path)
    project = registry.project(project_key)
    item_kind = kind or next(iter(project.kinds.keys()))
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            report = await import_json_items(
                source,
                project_key,
                registry,
                session,
                kind=item_kind,
                default_status=default_status,
                tags=tags or None,
                applies_to=applies_to,
                status_map=status_map,
                mapping=mapping,
                dry_run=dry_run,
            )
            label = "dry-run" if dry_run else "ok"
            print(
                f"[{label}] objects={report.objects_found} "
                f"skipped={report.objects_skipped} "
                f"planned={report.items_planned} "
                f"written={report.items_written} "
                f"status_mapped={report.status_mapped} "
                f"custom_fields={report.custom_fields} "
                f"external_links={report.external_links}",
                file=sys.stderr,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        await engine.dispose()
    return 0
