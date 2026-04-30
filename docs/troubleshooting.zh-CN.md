# 首次运行故障排查

[English](troubleshooting.md) | 简体中文

如果快速开始没有成功打开
`http://127.0.0.1:8765/dashboard/example`，可以按这份指南排查。

## 缺少 `uv`

先安装 `uv`，然后重新打开终端，让新命令进入 `PATH`。

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

如果 `uv --version` 仍然失败，检查安装器添加的目录是否已经加入 `PATH`，
然后重新打开一个终端会话。

## 8765 端口已被占用

可以换一个端口运行 demo：

```bash
uv run issuedeck demo --port 8775 --open
```

PowerShell:

```powershell
uv run issuedeck demo --port 8775 --open
```

如果是长期运行服务，可以传 `--port`：

```bash
uv run issuedeck serve --config server.toml --port 8775
```

也可以设置环境变量：

```bash
export ISSUEDECK_PORT=8775
```

PowerShell:

```powershell
$env:ISSUEDECK_PORT = "8775"
```

然后打开 `http://127.0.0.1:8775/dashboard/example`。

## Dashboard token 登录失败

`uv run issuedeck demo` 的默认本地 token 是：

```text
issuedeck-local-token
```

如果是正式配置的服务，Dashboard 登录需要 admin token。推荐通过环境变量设置：

```bash
export ISSUEDECK_API_TOKEN="your-secret-token"
uv run issuedeck serve --config server.toml
```

PowerShell:

```powershell
$env:ISSUEDECK_API_TOKEN = "your-secret-token"
uv run issuedeck serve --config server.toml
```

常见原因：

- 修改了 `.env` 或 `server.toml`，但没有重启服务。
- 使用了 `agent` 或 `read` scoped token。Dashboard 登录需要 `admin` token
  或旧版 `api_token`。
- 浏览器里有旧的 Dashboard 会话。退出登录，或清除
  `issuedeck_dashboard_session` cookie 后重新登录。

## SQLite 迁移错误

`demo`、`serve`、`seed-demo` 和 `import-github-url` 命令都会自动执行数据库迁移。
如果你直接调用 Alembic，可以运行：

```bash
uv run alembic upgrade head
```

如果数据库路径不对，检查 `server.toml` 里的 `data_dir`，并创建目录：

```bash
mkdir -p data
uv run alembic upgrade head
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force data
uv run alembic upgrade head
```

如果 SQLite 报 database is locked，先停止其他正在使用同一个
`data/tracker.db` 的 IssueDeck 服务，再重试。

## Docker Compose 启动失败

从干净的本地配置开始：

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

常见原因：

- Docker Desktop 没有运行。
- `8765` 端口已经被其他进程占用。
- `.env` 里的 `ISSUEDECK_API_TOKEN` 为空或不是预期值。
- 本地 `data/` 目录对容器不可写。

如果要换宿主机端口，可以编辑 `docker-compose.yml` 里的 `ports` 映射；
调试阶段也可以先用本地 `uv` 服务配合 `--port` 运行。

## 重置本地 demo

如果明确要重新写入 fake demo 数据：

```bash
uv run issuedeck demo --force-reset-demo-data --open
```

这个命令只会重置当前配置里的 demo 项目事项。不要对真实项目数据使用，除非你
明确想替换这份 demo 数据集。
