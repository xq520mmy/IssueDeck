# Docker Compose 加固示例

[English](docker-compose-hardening.md)

默认 `docker-compose.yml` 故意保持很小，方便第一次运行。把自托管 IssueDeck 从
本地 demo 搬到小型私有服务器时，可以参考这份检查清单。

## 加固示例

这个示例把 IssueDeck 只绑定在 localhost，固定 release 镜像，把数据放在 host
目录，并把 TLS/路由交给 Caddy、Nginx、Traefik 等反向代理。

```yaml
services:
  issuedeck:
    image: ${ISSUEDECK_IMAGE:-ghcr.io/xq520mmy/issuedeck:0.3.0}
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

启动前先创建 host 目录：

```bash
mkdir -p data backups projects
cp server.toml.example server.toml
cp .env.example .env
```

然后编辑 `.env`，写入随机 token：

```env
ISSUEDECK_API_TOKEN=replace-with-random-token
ISSUEDECK_PORT=8765
ISSUEDECK_IMAGE=ghcr.io/xq520mmy/issuedeck:0.3.0
```

## 反向代理假设

- 在反向代理层终止 HTTPS。
- 将流量转发到 `http://127.0.0.1:8765`。
- 通过 `127.0.0.1` 端口绑定，避免 IssueDeck 直接暴露在公网 Docker bridge 上。
- 如果服务只给团队内部使用，在代理或网络层增加访问控制。

最小 Caddy 示例：

```caddyfile
issuedeck.example.com {
  reverse_proxy 127.0.0.1:8765
}
```

## 备份计划

使用仓库内置的 host-side 备份脚本。它会通过运行中的容器创建一致的 SQLite 备份，
并清理过期快照。

```bash
chmod +x scripts/backup.sh
ISSUEDECK_BACKUP_DIR=/opt/issuedeck/backups ./scripts/backup.sh
```

Cron 示例：

```cron
0 3 * * * cd /opt/issuedeck && ISSUEDECK_BACKUP_RETENTION_DAYS=14 ./scripts/backup.sh >> /var/log/issuedeck-backup.log 2>&1
```

依赖备份前先做 smoke test：

```bash
python scripts/restore_smoke.py backups/tracker-YYYYMMDD-HHMMSS.db.gz \
  --out /tmp/issuedeck-restore-smoke.db
```

## 版本升级

生产环境建议固定 release tag，不要长期使用 `latest`。升级方式：

```bash
ISSUEDECK_IMAGE=ghcr.io/xq520mmy/issuedeck:0.3.0 docker compose pull
ISSUEDECK_IMAGE=ghcr.io/xq520mmy/issuedeck:0.3.0 docker compose up -d
curl -fsS http://127.0.0.1:8765/readyz
```

后续版本把 `0.3.0` 替换成目标 release tag。新容器通过 `/readyz` 前，保留旧数据库备份。
