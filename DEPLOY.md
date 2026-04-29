# Deploy IssueDeck

This guide covers a small self-hosted deployment with Docker Compose. It is
intended for teams that want a private IssueDeck service backed by SQLite.

## Files

- `Dockerfile` builds the app image.
- `docker-compose.yml` runs the service, mounts `/app/data`, and reads
  `ISSUEDECK_API_TOKEN` from `.env`.
- `server.toml.example` is the server configuration template.
- `projects/example.toml` is a safe demo project config.
- `scripts/backup.sh` creates SQLite backups from a running container.

## Local Docker Run

```bash
cp server.toml.example server.toml
cp .env.example .env

# Replace the placeholder token before sharing the service.
docker compose up -d --build
```

Open `http://127.0.0.1:8765/dashboard/example` and sign in with the
`ISSUEDECK_API_TOKEN` value from `.env`.

Health checks:

```bash
curl http://127.0.0.1:8765/healthz
curl http://127.0.0.1:8765/readyz
```

## Production Checklist

- Set a random `ISSUEDECK_API_TOKEN`; do not use `change-me`.
- Keep `server.toml`, `.env`, `data/`, `backups/`, and generated archives out
  of Git.
- Put the service behind a trusted network boundary or reverse proxy.
- Enable HTTPS at the proxy when the dashboard is accessed across a network.
- Back up the SQLite database regularly.
- Rotate the shared token when team membership changes.

Generate a token:

```bash
openssl rand -hex 32
```

Use it in `.env`:

```env
ISSUEDECK_API_TOKEN=replace-with-random-token
ISSUEDECK_PORT=8765
```

## Offline Image Transfer

On a machine with internet access:

```bash
docker build -t issuedeck:latest .
docker save issuedeck:latest | gzip > issuedeck-image.tar.gz
```

Copy `issuedeck-image.tar.gz`, `docker-compose.yml`, `server.toml`,
`projects/`, and `.env` to the target server. On the server:

```bash
docker load < issuedeck-image.tar.gz
docker compose up -d
```

If the compose file still uses `build: .`, replace it with:

```yaml
image: issuedeck:latest
```

## Backups

Run the bundled backup helper from the deployment directory:

```bash
chmod +x scripts/backup.sh
./scripts/backup.sh
```

For daily backups, add a cron entry:

```cron
0 3 * * * /opt/issuedeck/scripts/backup.sh >> /var/log/issuedeck-backup.log 2>&1
```

By default, backups are written under `backups/` and retained for 14 days.
Override the retention window with `ISSUEDECK_BACKUP_RETENTION_DAYS`.

## MCP Client

Point your MCP client at the deployed HTTP service:

```json
{
  "mcpServers": {
    "issuedeck": {
      "command": "uv",
      "args": ["run", "python", "-m", "issuedeck.mcp"],
      "env": {
        "ISSUEDECK_BASE_URL": "http://127.0.0.1:8765",
        "ISSUEDECK_TOKEN": "replace-with-random-token"
      }
    }
  }
}
```

`ISSUEDECK_TOKEN` is used by MCP clients. `ISSUEDECK_API_TOKEN` is used by the
server. They are usually the same secret value, but the variable names are
different because they live in different processes.
