"""CLI entry point. Subcommands for local demo, server, import, export, and MCP."""

from __future__ import annotations

import argparse
import asyncio
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
        help="Add CSV column aliases, e.g. title=Issue, status=Workflow",
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
        help="Add JSON field aliases, e.g. title=Issue, status=Workflow",
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
                f"external_links={report.external_links}",
                file=sys.stderr,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        await engine.dispose()
    return 0
