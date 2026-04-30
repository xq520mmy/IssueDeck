# Docker Compose Hardening

[简体中文](docker-compose-hardening.zh-CN.md)

The default `docker-compose.yml` is intentionally small so the first run is
easy. Use this checklist when moving a self-hosted IssueDeck instance from a
local demo to a small private server.

## Hardened Example

This example keeps IssueDeck on localhost, pins the release image, stores data
on the host, and leaves TLS/routing to a reverse proxy such as Caddy, Nginx, or
Traefik.

```yaml
services:
  issuedeck:
    image: ${ISSUEDECK_IMAGE:-ghcr.io/xq520mmy/issuedeck:0.3.2}
    container_name: issuedeck
    restart: unless-stopped
    init: true
    ports:
      - "127.0.0.1:${ISSUEDECK_PORT:-8765}:8765"
    volumes:
      - ./data:/app/data
      - ./projects:/app/projects:ro
      - ./server.toml:/app/server.toml:ro
    environment:
      ISSUEDECK_API_TOKEN: "${ISSUEDECK_API_TOKEN:?set ISSUEDECK_API_TOKEN in .env}"
      PYTHONDONTWRITEBYTECODE: "1"
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://localhost:8765/readyz')",
        ]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
```

Create the host directories before starting:

```bash
mkdir -p data backups projects
cp server.toml.example server.toml
cp .env.example .env
```

Then edit `.env` and set a random token:

```env
ISSUEDECK_API_TOKEN=replace-with-random-token
ISSUEDECK_PORT=8765
ISSUEDECK_IMAGE=ghcr.io/xq520mmy/issuedeck:0.3.2
```

## Reverse Proxy Assumptions

- Terminate HTTPS at the proxy.
- Forward traffic to `http://127.0.0.1:8765`.
- Keep IssueDeck off the public Docker bridge by binding the port to
  `127.0.0.1`.
- Add your normal access controls at the proxy or network layer if the service
  should stay private.

Minimal Caddy example:

```caddyfile
issuedeck.example.com {
  reverse_proxy 127.0.0.1:8765
}
```

## Backup Scheduling

Use the included host-side backup script. It creates a consistent SQLite backup
through the running container and prunes old snapshots.

```bash
chmod +x scripts/backup.sh
ISSUEDECK_BACKUP_DIR=/opt/issuedeck/backups ./scripts/backup.sh
```

Cron example:

```cron
0 3 * * * cd /opt/issuedeck && ISSUEDECK_BACKUP_RETENTION_DAYS=14 ./scripts/backup.sh >> /var/log/issuedeck-backup.log 2>&1
```

Smoke-test a backup before relying on it:

```bash
python scripts/restore_smoke.py backups/tracker-YYYYMMDD-HHMMSS.db.gz \
  --out /tmp/issuedeck-restore-smoke.db
```

## Release Updates

Pin production to a release tag, not `latest`. To upgrade:

```bash
ISSUEDECK_IMAGE=ghcr.io/xq520mmy/issuedeck:0.3.2 docker compose pull
ISSUEDECK_IMAGE=ghcr.io/xq520mmy/issuedeck:0.3.2 docker compose up -d
curl -fsS http://127.0.0.1:8765/readyz
```

For future releases, replace `0.3.2` with the target release tag and keep the
old database backup until the new container has passed `/readyz`.
