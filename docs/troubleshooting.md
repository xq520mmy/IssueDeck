# First-run Troubleshooting

English | [简体中文](troubleshooting.zh-CN.md)

Use this guide when the quickstart does not reach a working dashboard at
`http://127.0.0.1:8765/dashboard/example`.

## `uv` Is Missing

Install `uv`, then reopen your terminal so the new command is on `PATH`.

macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv --version
```

If `uv --version` still fails, check that the installer-added directory is on
`PATH`, then open a new terminal session.

## Port 8765 Is Already in Use

Run the demo on another port:

```bash
uv run issuedeck demo --port 8775 --open
```

PowerShell:

```powershell
uv run issuedeck demo --port 8775 --open
```

For a persistent server, either pass `--port`:

```bash
uv run issuedeck serve --config server.toml --port 8775
```

or set the environment variable:

```bash
export ISSUEDECK_PORT=8775
```

PowerShell:

```powershell
$env:ISSUEDECK_PORT = "8775"
```

Then open `http://127.0.0.1:8775/dashboard/example`.

## Dashboard Token Fails

For `uv run issuedeck demo`, the default local token is:

```text
issuedeck-local-token
```

For a configured server, the dashboard login uses an admin token. Prefer the
environment variable:

```bash
export ISSUEDECK_API_TOKEN="your-secret-token"
uv run issuedeck serve --config server.toml
```

PowerShell:

```powershell
$env:ISSUEDECK_API_TOKEN = "your-secret-token"
uv run issuedeck serve --config server.toml
```

Common causes:

- You changed `.env` or `server.toml` but did not restart the server.
- You are using an `agent` or `read` scoped token. Dashboard login requires an
  `admin` token or the legacy `api_token`.
- Your browser has an old dashboard session. Sign out or clear the
  `issuedeck_dashboard_session` cookie, then sign in again.

## SQLite Migration Errors

The demo command runs migrations automatically. For manual server startup, run:

```bash
uv run alembic upgrade head
uv run issuedeck serve --config server.toml
```

If the database path is wrong, confirm `data_dir` in `server.toml` and create
the directory if needed:

```bash
mkdir -p data
uv run alembic upgrade head
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force data
uv run alembic upgrade head
```

If SQLite reports the database is locked, stop any other running IssueDeck
server that is using the same `data/tracker.db`, then retry.

## Docker Compose Does Not Start

Start from a clean local config:

```bash
cp server.toml.example server.toml
cp .env.example .env
docker compose pull
docker compose up -d
docker compose logs --tail=80 issuedeck
curl -fsS http://127.0.0.1:8765/readyz
```

PowerShell:

```powershell
Copy-Item server.toml.example server.toml
Copy-Item .env.example .env
docker compose pull
docker compose up -d
docker compose logs --tail=80 issuedeck
curl.exe -fsS http://127.0.0.1:8765/readyz
```

Common causes:

- Docker Desktop is not running.
- Port `8765` is already used by another process.
- `.env` has an empty or unexpected `ISSUEDECK_API_TOKEN`.
- Local `data/` is not writable by the container.

To use a different host port, edit the `ports` mapping in `docker-compose.yml`
or run the local `uv` server with `--port` while debugging.

## Reset the Local Demo

To reseed the fake demo project intentionally:

```bash
uv run issuedeck demo --force-reset-demo-data --open
```

This only resets the configured demo project's IssueDeck items. Do not use it
against real project data unless you intentionally want to replace that demo
dataset.
