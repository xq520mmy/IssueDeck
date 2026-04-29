"""CLI entry point. Subcommands: serve / migrate / export / mcp."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="issuedeck")
    sub = parser.add_subparsers(dest="cmd")

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
