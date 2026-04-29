# IssueDeck

[English](README.md) | 简体中文

[![CI](https://github.com/xq520mmy/IssueDeck/actions/workflows/ci.yml/badge.svg)](https://github.com/xq520mmy/IssueDeck/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/xq520mmy/IssueDeck?display_name=tag)](https://github.com/xq520mmy/IssueDeck/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

<p align="center">
  <img src="docs/assets/issuedeck-social-preview.png" alt="IssueDeck：面向人和 AI coding agent 的本地优先事项看板" width="100%">
</p>

**比 Jira 更轻，比 Markdown 更稳。**

IssueDeck 是一个轻量、自托管的开发事项追踪器，面向小团队和 AI coding
工作流。它用一个 FastAPI + SQLite 服务管理多个项目，提供 Web Dashboard
给人使用，也提供 MCP tools 给 coding agent 使用。

## 为什么用 IssueDeck

- 用结构化服务替代散落在项目里的 Markdown tracker，事项、commit、分支和
  release 记录都在同一个地方。
- Dashboard 给人看，MCP tools 给 coding agent 调用，避免维护两套互相脱节的流程。
- 公开演示可以直接使用假数据，等准备好后再接入真实项目配置。

![IssueDeck dashboard demo](docs/assets/issuedeck-demo.gif)

## 功能

- 面向 Agent：MCP tools 让 coding agent 可以直接创建、更新、搜索、关联和发布事项。
- 多项目：每个项目独立配置事项类型、状态、分支和 ID 前缀。
- SQLite FTS5 全文搜索。
- 双向关系：`blocks` / `blocked_by` / `related_to`。
- Activity Timeline：自动记录生命周期事件，也支持手动评论。
- Dashboard 工作队列：最近更新、待办、进行中、被阻塞、待发布、已完成、已删除。
- 软删除和恢复。
- Ship 记录：绑定版本和 commit。
- Markdown 导出和通用 frontmatter 迁移。
- Dashboard 新建项目入口和语言切换基础。
- MCP tools，方便 coding agent 直接操作事项。

## 快速开始

```bash
uv sync
cp server.toml.example server.toml
uv run alembic upgrade head
uv run issuedeck seed-demo --config server.toml --project-key example
uv run issuedeck serve --config server.toml
```

打开 `http://127.0.0.1:8765/`，使用 `server.toml` 里的 `api_token` 登录。

## 假数据

公开截图、README 动图、本地演示都应该使用假数据：

```bash
uv run issuedeck seed-demo --config server.toml --project-key example
```

如果目标项目已经有事项，命令会拒绝覆盖。确认要替换该项目事项时再加
`--force-reset`。

## 配置项目

项目配置位于 `projects/*.toml`。Dashboard 也提供了轻量的新建项目入口，
会生成默认的 Feature / Bug / Improvement 类型和 Proposed / In Progress /
Done / Won't Fix 状态。高级配置仍建议直接编辑 TOML。

## MCP

MCP 进程通过 REST API 与 IssueDeck 通信，不直接访问 SQLite。环境变量：

```bash
ISSUEDECK_BASE_URL=http://127.0.0.1:8765
ISSUEDECK_TOKEN=your-secret-token
```

## 开源发布提醒

`data/*` 和除 `projects/example.toml` 之外的项目配置已经被 `.gitignore`
忽略。发布前请确认本地真实项目数据没有被加入 git。

## License

MIT. See [LICENSE](LICENSE).

路线图见 [ROADMAP.md](ROADMAP.md)。
