# IssueDeck

[English](README.md) | 简体中文

[![CI](https://github.com/xq520mmy/IssueDeck/actions/workflows/ci.yml/badge.svg)](https://github.com/xq520mmy/IssueDeck/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/xq520mmy/IssueDeck?display_name=tag)](https://github.com/xq520mmy/IssueDeck/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

<p align="center">
  <img src="docs/assets/issuedeck-social-preview.png" alt="IssueDeck：面向人和 AI coding agent 的本地优先事项看板" width="100%">
</p>

**比 Jira 更轻，比 Markdown 更稳。**

IssueDeck 是一个本地优先、自托管的事项看板，面向小团队和 AI coding
工作流。它用一套 FastAPI + SQLite 服务管理多个项目，给人提供 Web
Dashboard，也给 coding agent 提供 MCP tools。

## 为什么用 IssueDeck

- 用结构化服务替代散落在项目里的 Markdown tracker，让事项、commit、分支和
  release 记录放在同一个地方。
- 人用 Dashboard，agent 用 MCP tools，避免维护两套互相脱节的流程。
- 开源演示默认使用假数据，准备好后再接入真实项目配置。

![IssueDeck dashboard demo](docs/assets/issuedeck-demo.gif)

更多界面见[截图画廊](docs/gallery.zh-CN.md)，包括列表、看板、详情、搜索和新建项目。

## 功能

- 面向 Agent：MCP tools 可创建、更新、搜索、关联和发布事项。
- 多项目：每个项目独立配置事项类型、状态、分支和 ID 前缀。
- SQLite FTS5 全文搜索。
- 双向关系：`blocks`、`blocked_by`、`related_to`。
- 外部链接：关联 GitHub issue、PR、commit 和其他审查上下文。
- Activity Timeline：自动记录生命周期事件，也支持手动评论。
- Dashboard 工作队列：最近更新、待办、进行中、被阻塞、待发布、已完成、已删除。
- 已保存筛选：每个项目保存常用视图，例如活跃 Bug、阻塞事项和待发布队列。
- 软删除和恢复。
- Ship 记录：绑定版本和 commit。
- Markdown 导出和通用 frontmatter 迁移。
- Dashboard 新建项目入口和中英文切换。

## 快速开始

本地 demo：

```bash
uv run issuedeck demo
```

这个命令会在缺少 `server.toml` 时生成本地 demo 配置，执行数据库迁移，写入
`example` 项目的假数据，并启动 Dashboard。打开
`http://127.0.0.1:8765/dashboard/example`，使用 `issuedeck-local-token` 登录。

自动打开浏览器：

```bash
uv run issuedeck demo --open
```

## Docker

默认 Compose 文件会拉取 GitHub Container Registry 上的公开镜像：

```bash
cp server.toml.example server.toml
cp .env.example .env
docker compose pull
docker compose up -d
```

打开 `http://127.0.0.1:8765/dashboard/example`，使用 `.env` 里的
`ISSUEDECK_API_TOKEN` 登录。

如果要运行本地源码构建的镜像：

```bash
docker build -t issuedeck:local .
ISSUEDECK_IMAGE=issuedeck:local docker compose up -d
```

更完整的服务器部署、离线迁移、备份和恢复说明见
[中文部署指南](docs/deployment.zh.md)。

## 假数据

公开截图、README 动图、本地演示都应该使用假数据：

```bash
uv run issuedeck seed-demo --config server.toml --project-key example
```

如果目标项目已经有事项，命令会拒绝覆盖。确认要替换该项目事项时再加
`--force-reset`。

## 配置项目

`api_token` 会继续作为兼容旧部署的 admin token。需要给多个客户端分配权限时，
可以在 `server.toml` 里增加 scoped tokens：

```toml
[[tokens]]
name = "readonly"
token = "replace-with-readonly-token"
scopes = ["read"]

[[tokens]]
name = "agent"
token = "replace-with-agent-token"
scopes = ["agent"]

[[tokens]]
name = "admin-dashboard"
token = "replace-with-admin-token"
scopes = ["admin"]
```

`read` token 只能调用只读 API；`agent` token 可读写 REST API，适合 MCP /
coding agent；`admin` token 拥有完整 API 权限，也可以登录 Dashboard。

项目配置位于 `projects/*.toml`。Dashboard 也提供轻量的新建项目入口，会生成默认的
Feature / Bug / Improvement 类型和 Proposed / In Progress / Done / Won't Fix
状态。高级配置仍建议直接编辑 TOML。

## MCP

客户端配置示例见 [MCP 客户端接入](docs/mcp-clients.zh-CN.md)。

MCP 进程通过 REST API 与 IssueDeck 通信，不直接访问 SQLite。环境变量：

```bash
ISSUEDECK_BASE_URL=http://127.0.0.1:8765
ISSUEDECK_TOKEN=your-secret-token
```

## Markdown 迁移

导入器支持标准 frontmatter 字段，也默认识别 `type`、`state`、`labels` 等常见别名。
完整 schema 和自定义别名示例见
[Markdown Frontmatter 导入](docs/markdown-frontmatter-import.zh-CN.md)。

## 开源发布提醒

`data/*` 和除 `projects/example.toml` 之外的项目配置已经被 `.gitignore` 忽略。
发版前请确认本地真实项目数据没有被加入 git。

## License

MIT. See [LICENSE](LICENSE).

路线图见 [ROADMAP.md](ROADMAP.md)。
