# issuedeck 部署文档

## 目录

- [架构概览](#架构概览)
- [环境要求](#环境要求)
- [方式一：本地部署](#方式一本地部署)
- [方式二：Docker 部署](#方式二docker-部署)
- [配置说明](#配置说明)
- [接入 MCP 客户端](#接入-mcp-客户端)
- [数据迁移](#数据迁移)
- [数据导出与备份](#数据导出与备份)
- [运维操作](#运维操作)
- [常见问题](#常见问题)

---

## 架构概览

```
┌─────────────┐         HTTP/REST          ┌──────────────────┐
│ Claude Code │ ───── MCP stdio ────────── │  issuedeck MCP    │
│ / 其他 MCP  │                            │  (python -m      │
│   客户端    │                            │   issuedeck.mcp)  │
└─────────────┘                            └────────┬─────────┘
                                                    │ httpx
                                                    ▼
                                           ┌──────────────────┐
                                           │  issuedeck server  │
                                           │  (FastAPI/uvicorn)│
                                           │  :8765            │
                                           └────────┬─────────┘
                                                    │ SQLAlchemy async
                                                    ▼
                                           ┌──────────────────┐
                                           │  SQLite (WAL)    │
                                           │  data/tracker.db │
                                           └──────────────────┘
```

- **issuedeck server** — FastAPI REST 服务，管理所有项目的 items、关系、搜索、ship 记录
- **issuedeck MCP** — stdio 进程，作为 MCP server 注册到 Claude Code 等客户端，内部通过 httpx 调 REST API
- **SQLite** — 单文件数据库，WAL 模式，支持 FTS5 全文搜索

---

## 环境要求

| 部署方式 | 要求 |
|---------|------|
| 本地部署 | Python >= 3.11, [uv](https://docs.astral.sh/uv/) |
| Docker 部署 | Docker >= 20.10, Docker Compose V2 |

---

## 方式一：本地部署

### 1. 安装依赖

```bash
cd issuedeck
uv sync
```

### 2. 准备配置文件

```bash
# 服务配置
cp server.toml.example server.toml

# 项目配置（可创建多个）
cp projects/example.toml projects/myproject.toml
```

编辑 `projects/myproject.toml`，文件名必须与 `key` 字段一致：

```toml
key = "myproject"
name = "我的项目"
description = "项目描述"

[kinds.feature]
label = "Feature"
prefix = "FEAT"

[kinds.bug]
label = "Bug"
prefix = "BUG"

[statuses.proposed]
label = "待处理"

[statuses.in_progress]
label = "进行中"

[statuses.done]
label = "已完成"
terminal = true
requires_ship = true

[[branches]]
key = "main"
label = "Main"
```

### 3. 初始化数据库

```bash
uv run alembic upgrade head
```

数据库文件默认在 `./data/tracker.db`。

### 4. 启动服务

```bash
# 设置 API Token（必需）
export ISSUEDECK_API_TOKEN="your-secret-token"

# 启动
uv run issuedeck serve --config server.toml
```

### 5. 验证

```bash
# 健康检查（不需要 token）
curl http://127.0.0.1:8765/healthz
# 返回: {"status":"ok","version":"0.1.0"}

# 项目列表（需要 token）
curl -H "Authorization: Bearer your-secret-token" \
     http://127.0.0.1:8765/api/v1/projects
```

---

## 方式二：Docker 部署

### 1. 准备配置文件

与本地部署相同，准备好 `server.toml` 和 `projects/*.toml`。

```bash
cp server.toml.example server.toml
# 编辑 server.toml 和项目配置...
```

> **注意：** `server.toml` 中 `data_dir` 和 `projects_dir` 保持默认即可（`./data` 和 `./projects`），容器内会通过 volume 挂载。

### 2. 设置环境变量

创建 `.env` 文件（可选，也可直接 export）：

```bash
# .env
ISSUEDECK_API_TOKEN=your-secret-token
ISSUEDECK_PORT=8765
```

### 3. 构建并启动

```bash
# 构建镜像并启动
docker compose up -d --build

# 查看日志
docker compose logs -f issuedeck

# 查看健康状态
docker compose ps
```

### 4. 验证

```bash
curl http://localhost:8765/healthz
```

浏览器打开 `http://localhost:8765/dashboard/<project-key>` 时，需要输入
`ISSUEDECK_API_TOKEN` 登录。REST API 和 MCP 客户端仍然使用 Bearer token。


### 5. 常用 Docker 命令

```bash
# 停止
docker compose down

# 停止并删除数据卷（危险！会丢失所有数据）
docker compose down -v

# 重新构建（代码有更新时）
docker compose up -d --build

# 进入容器排查问题
docker compose exec issuedeck bash
```

### 6. 预构建镜像

如果要把镜像推到私有仓库：

```bash
# 构建并打 tag
docker build -t your-registry/issuedeck:0.1.0 .
docker tag your-registry/issuedeck:0.1.0 your-registry/issuedeck:latest

# 推送
docker push your-registry/issuedeck:0.1.0
docker push your-registry/issuedeck:latest
```

使用预构建镜像时，修改 `docker-compose.yml`：

```yaml
services:
  issuedeck:
    image: your-registry/issuedeck:0.1.0   # 替换 build: .
    # ... 其余配置不变
```

---

## 配置说明

### server.toml

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | string | `"0.0.0.0"` | 监听地址 |
| `port` | int | `8765` | 监听端口 |
| `api_token` | string | - | API 认证 token，**建议通过 `ISSUEDECK_API_TOKEN` 环境变量设置** |
| `data_dir` | string | `"./data"` | SQLite 数据库目录 |
| `projects_dir` | string | `"./projects"` | 项目配置 TOML 文件目录 |
| `log_level` | string | `"info"` | 日志级别：debug / info / warning / error |
| `sqlite.wal_mode` | bool | `true` | 启用 WAL 模式（推荐） |
| `sqlite.busy_timeout_ms` | int | `5000` | SQLite 锁等待超时（毫秒） |

### 环境变量覆盖

以下环境变量会覆盖 `server.toml` 中的对应字段：

| 环境变量 | 覆盖字段 |
|---------|---------|
| `ISSUEDECK_API_TOKEN` | `api_token` |
| `ISSUEDECK_HOST` | `host` |
| `ISSUEDECK_PORT` | `port` |
| `ISSUEDECK_DATA_DIR` | `data_dir` |
| `ISSUEDECK_PROJECTS_DIR` | `projects_dir` |

### 项目配置 (projects/*.toml)

每个 `.toml` 文件定义一个项目。文件名必须与 `key` 字段一致。

| 字段 | 说明 |
|------|------|
| `key` | 项目唯一标识，等于文件名（不含 .toml） |
| `name` | 项目显示名 |
| `description` | 项目描述 |
| `kinds.*` | Item 类型，每个类型有 `label` 和 `prefix`（大写，如 `FEAT`） |
| `statuses.*` | 状态，可选 `terminal=true`（终态）和 `requires_ship=true` |
| `branches[]` | 分支列表，每个有 `key` 和 `label` |
| `id_format.digits` | 本地 ID 数字位数，默认 4（即 FEAT-0001） |

---

## 接入 MCP 客户端

### Claude Code

在项目的 `.mcp.json` 或全局 MCP 配置中添加：

```json
{
  "mcpServers": {
    "issuedeck": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/issuedeck", "python", "-m", "issuedeck.mcp"],
      "env": {
        "ISSUEDECK_BASE_URL": "http://127.0.0.1:8765",
        "ISSUEDECK_TOKEN": "your-secret-token"
      }
    }
  }
}
```

> Docker 部署时 `ISSUEDECK_BASE_URL` 用 `http://host.docker.internal:8765`（如果 MCP 进程也在容器内）或 `http://127.0.0.1:8765`（MCP 进程在宿主机）。

### 可用工具（11 个）

| 工具 | 说明 |
|------|------|
| `list_projects` | 列出所有项目 |
| `get_project_config` | 获取项目配置（kinds/statuses/branches） |
| `create_item` | 创建 item |
| `update_item` | 更新 item（标题、内容、状态、标签等） |
| `ship_item` | 标记 item 已发布（绑定版本号和 commits） |
| `delete_item` | 软删除 item |
| `get_item` | 获取单个 item 详情（含关系和发布记录） |
| `list_items` | 列表查询，支持按 kind/status/tag/branch 筛选 + 游标分页 |
| `search_items` | FTS5 全文搜索 |
| `add_relationship` | 添加关系（blocks / related_to，自动创建双向） |
| `remove_relationship` | 删除关系（自动删除双向） |

---

## 数据迁移

### 从 Markdown frontmatter 迁移

```bash
# 预览（不写入）
uv run issuedeck migrate \
  --config server.toml \
  --from-frontmatter /path/to/markdown-tracker \
  --project-key myproject \
  --dry-run

# 确认无误后执行
uv run issuedeck migrate \
  --config server.toml \
  --from-frontmatter /path/to/markdown-tracker \
  --project-key myproject
```

Docker 环境中执行：

```bash
docker compose exec issuedeck uv run issuedeck migrate \
  --config server.toml \
  --from-frontmatter /data/markdown-source \
  --project-key myproject
```

迁移会：
1. 解析 `items/*.md` 和 `items/.archive/*.md` 的 frontmatter
2. 验证所有 kind/status/branch 是否在项目配置中定义
3. 一个事务写入全部数据（tags、applies_to、ship_records、commits）
4. 写入后校验行数

如果目标项目已有数据，需加 `--force-reset` 清空后重新导入。

---

## 数据导出与备份

### Markdown 导出

```bash
uv run issuedeck export \
  --config server.toml \
  --project-key myproject \
  --out ./export
```

每个 item 导出为一个 `.md` 文件（YAML frontmatter + body），便于继续使用文本化快照和代码审查。

### 数据库备份

SQLite 单文件，直接备份即可：

```bash
# 本地
cp data/tracker.db data/tracker.db.bak

# Docker
docker compose exec issuedeck cp /app/data/tracker.db /app/data/tracker.db.bak
docker compose cp issuedeck:/app/data/tracker.db.bak ./tracker.db.bak
```

> 建议在备份前确认没有正在写入的事务。WAL 模式下直接复制 `.db` 文件是安全的。

---

## 运维操作

### 数据库迁移（版本升级后）

代码更新后如果有新的 Alembic 迁移：

```bash
# 本地
uv run alembic upgrade head

# Docker（自动执行，重启即可）
docker compose up -d --build
```

Docker 容器的 `docker-entrypoint.sh` 在每次启动时会自动运行 `alembic upgrade head`。

### 查看数据库状态

```bash
# 当前迁移版本
uv run alembic current

# 迁移历史
uv run alembic history
```

### REST API 快速测试

```bash
TOKEN="your-secret-token"
BASE="http://127.0.0.1:8765"

# 创建 item
curl -X POST "$BASE/api/v1/projects/myproject/items" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"kind": "feature", "title": "新功能", "tags": ["v1"]}'

# 查询列表
curl "$BASE/api/v1/projects/myproject/items" \
  -H "Authorization: Bearer $TOKEN"

# 全文搜索
curl "$BASE/api/v1/projects/myproject/search?q=新功能" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 常见问题

### Q: 启动报 `ISSUEDECK_TOKEN env var is required`

这是 MCP 客户端的报错，不是 server。设置环境变量：

```bash
export ISSUEDECK_TOKEN="your-secret-token"
```

注意 MCP 进程用的是 `ISSUEDECK_TOKEN`，server 用的是 `ISSUEDECK_API_TOKEN`。

### Q: Docker 构建失败，提示 uv.lock 不存在

先在本地生成 lock 文件：

```bash
uv lock
```

然后重新构建。

### Q: SQLite 报 `database is locked`

调大 `server.toml` 中的 `sqlite.busy_timeout_ms`（默认 5000ms）。单进程部署下一般不会出现。

### Q: 如何添加多个项目？

在 `projects/` 目录下创建多个 `.toml` 文件，每个文件是一个项目。文件名要与 `key` 字段一致：

```bash
cp projects/example.toml projects/frontend.toml
# 编辑 frontend.toml，修改 key = "frontend"
```

重启服务后自动加载。

### Q: 如何在生产环境设置 HTTPS？

issuedeck 本身不处理 TLS。推荐在前面放 nginx 或 caddy 做反向代理：

```nginx
server {
    listen 443 ssl;
    server_name issuedeck.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```
