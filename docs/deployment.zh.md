# IssueDeck 部署指南

这份指南面向小团队或个人服务器部署，默认使用 Docker Compose 和 SQLite。

## 架构

```text
MCP client / Browser
        |
        | HTTP / REST
        v
IssueDeck server (FastAPI + uvicorn)
        |
        | SQLAlchemy async
        v
SQLite database (data/tracker.db)
```

- `issuedeck server`：FastAPI REST 服务，管理项目、事项、关系、搜索和发布记录。
- `issuedeck MCP`：stdio 进程，通过 HTTP 调用 REST API，不直接访问 SQLite。
- `SQLite`：单文件数据库，适合本地优先和小团队自托管。

## 环境要求

| 部署方式 | 要求 |
| --- | --- |
| 本地运行 | Python 3.11+、uv |
| Docker 部署 | Docker 20.10+、Docker Compose V2 |

## 方式一：本地运行

```bash
cp server.toml.example server.toml
uv sync
uv run alembic upgrade head
export ISSUEDECK_API_TOKEN="your-secret-token"
uv run issuedeck serve --config server.toml
```

打开 `http://127.0.0.1:8765/dashboard/example`，使用
`ISSUEDECK_API_TOKEN` 登录 Dashboard。

健康检查：

```bash
curl http://127.0.0.1:8765/healthz
curl http://127.0.0.1:8765/readyz
```

## 方式二：Docker Compose

默认 `docker-compose.yml` 会拉取公开镜像
`ghcr.io/xq520mmy/issuedeck:latest`：

```bash
cp server.toml.example server.toml
cp .env.example .env

# 先把 .env 里的 ISSUEDECK_API_TOKEN 改成随机值
docker compose pull
docker compose up -d
```

打开 `http://127.0.0.1:8765/dashboard/example`，使用 `.env` 里的
`ISSUEDECK_API_TOKEN` 登录。

查看状态：

```bash
docker compose ps
docker compose logs -f issuedeck
curl http://127.0.0.1:8765/readyz
```

生产环境建议固定版本，而不是长期使用 `latest`：

```bash
ISSUEDECK_IMAGE=ghcr.io/xq520mmy/issuedeck:0.4.0 docker compose up -d
```

可用镜像标签：

- `latest`：最新稳定 release。
- `0.4.0`、`0.4`、`v0.4.0`：版本标签。
- `edge`：最新 `main` 分支镜像。

如果要运行本地源码构建的镜像：

```bash
docker build -t issuedeck:local .
ISSUEDECK_IMAGE=issuedeck:local docker compose up -d
```

如果要把服务放到小型生产环境，建议参考
[Docker Compose 加固示例](docker-compose-hardening.zh-CN.md)，其中包含固定镜像版本、
只绑定 localhost、host-mounted data、日志限制、备份计划和反向代理假设。

## 生产检查清单

- 设置随机 `ISSUEDECK_API_TOKEN`，不要使用 `change-me`。
- 不要把 `.env`、`server.toml`、`data/`、`backups/` 提交到 git。
- 将服务放在可信网络、VPN 或反向代理后面。
- 通过公网访问 Dashboard 时，在反向代理层启用 HTTPS。
- 定期备份 SQLite 数据库。
- 团队成员变化时轮换 token。

生成随机 token：

```bash
openssl rand -hex 32
```

`.env` 示例：

```env
ISSUEDECK_API_TOKEN=replace-with-random-token
ISSUEDECK_PORT=8765
```

## 离线部署

在有网络的机器上：

```bash
docker pull ghcr.io/xq520mmy/issuedeck:latest
docker tag ghcr.io/xq520mmy/issuedeck:latest issuedeck:latest
docker save issuedeck:latest | gzip > issuedeck-image.tar.gz
```

把 `issuedeck-image.tar.gz`、`docker-compose.yml`、`server.toml`、`projects/`
和 `.env` 复制到目标服务器，然后运行：

```bash
docker load < issuedeck-image.tar.gz
ISSUEDECK_IMAGE=issuedeck:latest docker compose up -d
```

每个 GitHub Release 也会上传 Python wheel、source distribution 和
`SHA256SUMS.txt`。离线镜像或包文件进入内网前，建议先用 checksum 校验。

## 备份与恢复

运行仓库内置备份脚本。它会在运行中的容器里调用 SQLite online backup API，
再把 gzip 快照复制到 Docker host 的 `backups/` 目录：

```bash
chmod +x scripts/backup.sh
./scripts/backup.sh
```

每天凌晨 3 点备份：

```cron
0 3 * * * /opt/issuedeck/scripts/backup.sh >> /var/log/issuedeck-backup.log 2>&1
```

恢复前先做 smoke test：

```bash
python scripts/restore_smoke.py backups/tracker-YYYYMMDD-HHMMSS.db.gz \
  --out /tmp/issuedeck-restore-smoke.db
```

Docker 环境也可以直接跑：

```bash
docker compose run --rm \
  -v "$PWD/backups:/backups:ro" \
  -v "$PWD/tmp:/tmp/issuedeck" \
  issuedeck \
  python scripts/restore_smoke.py /backups/tracker-YYYYMMDD-HHMMSS.db.gz \
    --out /tmp/issuedeck/restore-smoke.db
```

确认备份可用后再恢复：

```bash
docker compose stop issuedeck
cp data/tracker.db data/tracker.db.before-restore
gzip -dc backups/tracker-YYYYMMDD-HHMMSS.db.gz > data/tracker.db
docker compose up -d
curl -fsS http://127.0.0.1:8765/readyz
```

恢复只替换 SQLite 数据库。`server.toml`、`.env` 和 `projects/*.toml` 不需要替换，
除非你正在恢复整台主机的快照。

## MCP 客户端

把 MCP 客户端指向已部署的 HTTP 服务：

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

`ISSUEDECK_TOKEN` 给 MCP 客户端使用；`ISSUEDECK_API_TOKEN` 给服务端使用。
它们通常是同一个 secret，但变量名不同，因为它们属于不同进程。

## 常见问题

### 启动时报 `ISSUEDECK_TOKEN env var is required`

这是 MCP 客户端进程的报错，不是 server。设置：

```bash
export ISSUEDECK_TOKEN="your-secret-token"
```

### Docker 镜像更新后如何升级

```bash
docker compose pull
docker compose up -d
curl -fsS http://127.0.0.1:8765/readyz
```

容器启动时会自动执行 `alembic upgrade head`。

### SQLite 报 `database is locked`

调大 `server.toml` 里的 `sqlite.busy_timeout_ms`。单进程部署下一般不会频繁出现。

### 如何添加多个项目

在 `projects/` 目录创建多个 `.toml` 文件。文件名要与 `key` 字段一致：

```bash
cp projects/example.toml projects/frontend.toml
# 编辑 frontend.toml，把 key 改成 "frontend"
docker compose restart issuedeck
```
