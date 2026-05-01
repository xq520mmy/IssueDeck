"""FastAPI application assembly."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from issuedeck import __version__
from issuedeck.core.auth import BearerTokenCredential, BearerTokenMiddleware
from issuedeck.core.config import (
    ConfigRegistry,
    load_project_config,
    load_server_config,
)
from issuedeck.core.db import make_engine, make_session_factory
from issuedeck.core.errors import ConfigError, install_error_handlers
from issuedeck.core.logging import configure_logging
from issuedeck.core.webhooks import WebhookDispatcher
from issuedeck.features.dashboard.routes import router as dashboard_router
from issuedeck.features.items.models import Item
from issuedeck.features.items.routes import router as items_router
from issuedeck.features.projects.routes import router as projects_router
from issuedeck.features.relationships.routes import router as relationships_router
from issuedeck.features.search.routes import router as search_router
from issuedeck.features.work_sessions.routes import router as work_sessions_router


def _build_registry(server_toml: Path) -> ConfigRegistry:
    server_cfg = load_server_config(server_toml)

    projects: dict = {}
    if server_cfg.projects_dir.exists():
        for toml_file in sorted(server_cfg.projects_dir.glob("*.toml")):
            pc = load_project_config(toml_file)
            if pc.key != toml_file.stem:
                raise ConfigError(
                    f"{toml_file}: key '{pc.key}' must equal filename stem "
                    f"'{toml_file.stem}'"
                )
            if pc.key in projects:
                raise ConfigError(f"duplicate project key '{pc.key}'")
            projects[pc.key] = pc

    return ConfigRegistry(server=server_cfg, projects=projects)


async def _validate_db_against_registry(
    session_factory, registry: ConfigRegistry,
) -> None:
    async with session_factory() as s:
        known = {p.key for p in registry.all_projects()}
        rows = (await s.execute(
            select(Item.project_key, Item.local_id, Item.kind, Item.status)
        )).all()
        orphans: list[str] = []
        for project_key, local_id, kind, status in rows:
            if project_key not in known:
                orphans.append(f"project '{project_key}' ({local_id})")
                continue
            pc = registry.project(project_key)
            if kind not in pc.kinds:
                orphans.append(f"kind '{kind}' in {project_key}/{local_id}")
            if status not in pc.statuses:
                orphans.append(f"status '{status}' in {project_key}/{local_id}")
        if orphans:
            lines = "\n  - ".join(orphans)
            raise ConfigError(
                "items table references values not declared in current config:\n"
                f"  - {lines}"
            )


def create_app(server_toml: Path | str) -> FastAPI:
    registry = _build_registry(Path(server_toml))
    server_cfg = registry.server

    configure_logging(server_cfg.log_level)

    server_cfg.data_dir.mkdir(parents=True, exist_ok=True)
    db_path = server_cfg.data_dir / "tracker.db"
    engine = make_engine(
        f"sqlite+aiosqlite:///{db_path}",
        busy_timeout_ms=server_cfg.sqlite.busy_timeout_ms,
    )
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await _validate_db_against_registry(session_factory, registry)
        yield
        await engine.dispose()

    app = FastAPI(title="IssueDeck", version=__version__, lifespan=lifespan)
    app.state.registry = registry
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.webhook_dispatcher = WebhookDispatcher(server_cfg.webhooks)

    install_error_handlers(app)
    app.add_middleware(
        BearerTokenMiddleware,
        tokens=[
            BearerTokenCredential(
                name=token.name,
                token=token.token.get_secret_value(),
                scopes=frozenset(token.normalized_scopes()),
            )
            for token in server_cfg.auth_tokens()
        ],
        exempt_paths=(
            "/",
            "/healthz",
            "/readyz",
            "/favicon.ico",
            "/dashboard/login",
            "/dashboard/language",
            "/dashboard/static",
        ),
        dashboard_paths=("/dashboard",),
    )

    # Projects router first so GET /api/v1/projects matches projects, not items
    app.include_router(projects_router)
    app.include_router(items_router)
    app.include_router(work_sessions_router)
    app.include_router(relationships_router)
    app.include_router(search_router)
    app.include_router(dashboard_router)

    static_dir = Path(__file__).resolve().parent / "features" / "dashboard" / "static"
    app.mount(
        "/dashboard/static",
        StaticFiles(directory=str(static_dir)),
        name="dashboard-static",
    )

    @app.get("/", include_in_schema=False)
    async def root():
        response = RedirectResponse(url="/dashboard/", status_code=303)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "version": __version__}

    @app.get("/readyz")
    async def readyz():
        return {
            "status": "ready",
            "version": __version__,
            "projects": len(registry.all_projects()),
        }

    return app
