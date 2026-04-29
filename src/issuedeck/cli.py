"""CLI entry point. Subcommands: demo / serve / migrate / export / mcp."""

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

    p_exp = sub.add_parser("export", help="Export project as markdown bundle")
    p_exp.add_argument("--config", default="server.toml")
    p_exp.add_argument("--project-key", required=True)
    p_exp.add_argument("--out", required=True, help="Output directory")

    p_seed = sub.add_parser("seed-demo", help="Seed fake demo data for docs/screenshots")
    p_seed.add_argument("--config", default="server.toml")
    p_seed.add_argument("--project-key", default="example")
    p_seed.add_argument("--force-reset", action="store_true")

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
        ))
    if args.cmd == "export":
        return asyncio.run(_cmd_export(
            Path(args.config), args.project_key, Path(args.out),
        ))
    if args.cmd == "seed-demo":
        return asyncio.run(_cmd_seed_demo(
            Path(args.config), args.project_key, args.force_reset,
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
    dry_run: bool, force_reset: bool,
) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.migrate.frontmatter import migrate_frontmatter_bundle

    registry = _build_registry(config_path)
    db_path = registry.server.data_dir / "tracker.db"
    engine = make_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            report = await migrate_frontmatter_bundle(
                source_dir=source_dir, project_key=project_key,
                registry=registry, db=session,
                dry_run=dry_run, force_reset=force_reset,
            )
            print(
                f"[{'dry-run' if dry_run else 'ok'}] planned={report.items_planned} "
                f"written={report.items_written} "
                f"ship_records={report.ship_records} "
                f"ship_commits={report.ship_commits}",
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


async def _cmd_seed_demo(
    config_path: Path, project_key: str, force_reset: bool,
) -> int:
    from issuedeck.core.db import make_engine, make_session_factory
    from issuedeck.features.demo.seed import seed_demo_project

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
