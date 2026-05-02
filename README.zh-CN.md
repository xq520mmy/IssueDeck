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

## 30 秒试用

直接运行 PyPI 最新正式版本，使用假数据启动本地 demo：

```bash
uvx issuedeck demo --open
```

不需要 clone，也不会接触你的真实项目数据。命令会创建本地 `example` 项目并打开
Dashboard，登录 token 是 `issuedeck-local-token`。

如果想试还没发布的 `main` 分支：

```bash
uvx --from git+https://github.com/xq520mmy/IssueDeck issuedeck demo --open
```

## 为什么用 IssueDeck

- 用结构化服务替代散落在项目里的 Markdown tracker，让事项、commit、分支和
  release 记录放在同一个地方。
- 人用 Dashboard，agent 用 MCP tools，避免维护两套互相脱节的流程。
- 开源演示默认使用假数据，准备好后再接入真实项目配置。

![IssueDeck dashboard demo](docs/assets/issuedeck-demo.gif)

更多界面见[截图画廊](docs/gallery.zh-CN.md)，包括列表、看板、详情、搜索和新建项目。
日常分诊快捷键见[键盘快捷键](docs/keyboard-shortcuts.zh-CN.md)。
Agent 交接和进展跟踪见 [Agent 工作会话](docs/agent-work-sessions.zh-CN.md)。
GitHub backlog 导入见 [GitHub Issues 导入](docs/github-issues-import.zh-CN.md)。
Dashboard CSV、JSON 和 Markdown 上传见
[Dashboard 文件导入](docs/dashboard-file-imports.zh-CN.md)。
重新打开历史导入批次见
[Dashboard 导入历史](docs/dashboard-import-history.zh-CN.md)。
导入后的批量整理见 [Dashboard 批量分诊](docs/dashboard-bulk-triage.zh-CN.md)。
新工作区起步配置见[项目模板](docs/project-templates.zh-CN.md)。
项目级额外元数据见[自定义字段](docs/custom-fields.zh-CN.md)。
项目快照归档见[审计导出包](docs/audit-bundles.zh-CN.md)。

## 功能

- 面向 Agent：MCP tools 可创建、更新、筛选、关联和发布事项，并支持自定义字段。
- Agent 工作会话：记录哪个 agent 正在处理哪个事项、目标、进展和最终结果。
- 多项目：每个项目独立配置事项类型、状态、分支和 ID 前缀。
- 项目自定义字段：为事项补充 priority、estimate、客户影响、来源 URL 等元数据，
  并支持列表摘要展示、Dashboard/API 精确/范围/有值筛选、批量更新和 CSV/JSON
  导入映射。
- SQLite FTS5 全文搜索。
- 双向关系：`blocks`、`blocked_by`、`related_to`。
- 外部链接：关联 GitHub issue、PR、commit 和其他审查上下文。
- GitHub URL helper：从 issue、PR、commit URL 创建带 external link 的
  IssueDeck item，不做完整同步。
- GitHub Issues 导入：可在 Dashboard 或 CLI 按 state/label 拉取仓库 issues，
  并跳过已导入项。
- CSV、JSON 和 Markdown task-list 导入：可从 Dashboard 或 CLI 把 tracker 导出、
  `TODO.md` 和 GitHub checklist 转成 IssueDeck item。
- Activity Timeline：自动记录生命周期事件，也支持手动评论。
- Slack、Discord 和邮件生命周期通知：把创建、更新、发布等事项变化同步给团队。
- Dashboard 工作队列：最近更新、待办、进行中、被阻塞、待发布、已完成、已删除。
- Dashboard 批量分诊：多选事项后批量更新状态、类型、标签、分支、删除和恢复。
- Dashboard 导入历史：重新打开最近的 GitHub、CSV、JSON 和 Markdown 导入批次。
- 已保存筛选：每个项目保存常用视图，例如活跃 Bug、阻塞事项和待发布队列。
- 软删除和恢复。
- Ship 记录：绑定版本和 commit。
- Markdown 导出、项目级审计 ZIP 快照和通用 frontmatter 迁移。
- Dashboard 新建项目模板、中英文切换、首次启动清单和键盘友好的分诊快捷键。

## 快速开始

不用 clone 仓库，直接运行 PyPI 最新正式版本：

```bash
uvx issuedeck demo --open
```

如果想试还没发布的 GitHub main 分支：

```bash
uvx --from git+https://github.com/xq520mmy/IssueDeck issuedeck demo --open
```

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

如果首次运行卡在 `uv`、端口占用、token、SQLite 迁移或 Docker Compose 启动
问题上，见[首次运行故障排查](docs/troubleshooting.zh-CN.md)。

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
[中文部署指南](docs/deployment.zh.md)。小型生产环境的 Compose 加固示例见
[Docker Compose 加固示例](docs/docker-compose-hardening.zh-CN.md)。

## 假数据

公开截图、README 动图、本地演示都应该使用假数据：

```bash
uv run issuedeck seed-demo --config server.toml --project-key example
```

如果目标项目已经有事项，命令会拒绝覆盖。确认要替换该项目事项时再加
`--force-reset`。

## CLI 事项工作流

不启动 Dashboard 也可以直接创建本地事项：

```bash
uv run issuedeck create-item \
  --config server.toml \
  --project-key example \
  --kind feature \
  --title "Add release checklist" \
  --tag ops \
  --custom-field priority=high \
  --external-link "Spec | https://example.com/spec"
```

短内容可以用 `--body`，较长 Markdown 可以用 `--body-file notes.md`，写入前可用
`--dry-run` 预览 payload。

同一套终端流程也可以更新已有事项：

```bash
uv run issuedeck update-item FEAT-0001 \
  --config server.toml \
  --project-key example \
  --status in_progress \
  --append-body-file notes.md \
  --custom-field estimate=5
```

`update-item` 可替换标题、状态、正文、标签、分支、自定义字段和外部链接。
需要移除全部外部链接时使用 `--clear-external-links`。

导入后的批量整理可以直接更新多个事项：

```bash
uv run issuedeck bulk-update-items FEAT-0001 FEAT-0002 \
  --config server.toml \
  --project-key example \
  --status in_progress \
  --tag triaged \
  --tag-mode replace
```

批量清理可用 `--action delete` 或 `--action restore`。批量更新也支持分支和自定义字段。

记录事项发布版本和 commit：

```bash
uv run issuedeck ship-item FEAT-0001 \
  --config server.toml \
  --project-key example \
  --branch main \
  --version v1.0.0 \
  --commit abc1234
```

追加评论、验证记录或交接事件：

```bash
uv run issuedeck append-item-event FEAT-0001 \
  --config server.toml \
  --project-key example \
  --event-type verification \
  --actor-type agent \
  --actor-name codex \
  --body "Checked locally before release."
```

不启动 Dashboard 也可以直接查看本地事项：

```bash
uv run issuedeck list-items \
  --config server.toml \
  --project-key example \
  --status in_progress \
  --custom-field 'estimate>=3'
```

脚本集成可以加 `--format json`。筛选项包括 `--kind`、`--status`、`--tag`、
`--applies-to`、`--relation-type`、`--custom-field`、`--include-deleted` 和
`--only-deleted`。

查看单个事项详情：

```bash
uv run issuedeck get-item FEAT-0001 --config server.toml --project-key example
```

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

项目配置位于 `projects/*.toml`。Dashboard 也提供轻量的新建项目入口，可以从
Basic issue deck、Agent workflow、Software team 等起步模板生成项目配置。
高级配置仍建议直接编辑 TOML。也可以通过 `project_templates_dir` 增加本地模板包；
详见[项目模板](docs/project-templates.zh-CN.md)。

同一套起步模板也可以从 CLI 使用：

```bash
uv run issuedeck list-project-templates --config server.toml
uv run issuedeck create-project myapp \
  --config server.toml \
  --name "My App" \
  --template agent
```

## Webhooks

IssueDeck 支持可选的签名生命周期 Webhooks，可以在事项创建、更新、发布、删除、
恢复时通知外部自动化系统。配置示例和签名校验方式见
[生命周期 Webhooks](docs/webhooks.zh-CN.md)，同一篇文档也包含 Slack 和 Discord
以及邮件团队通知配置。FastAPI、Flask、Node/Express 的 receiver 示例见
[Webhook Receiver 示例](docs/webhook-receivers.zh-CN.md)。

## GitHub URL Helper

从 GitHub issue、PR 或 commit URL 创建 IssueDeck item：

```bash
uv run issuedeck import-github-url \
  --config server.toml \
  --project-key example \
  --kind feature \
  https://github.com/example/repo/issues/42
```

加 `--dry-run` 可以先预览 create payload。详见
[GitHub URL 导入](docs/github-import.zh-CN.md)。

## GitHub Issues 导入

从仓库导入 open issues，并且之后重复运行时会跳过已经有相同 GitHub external link
的事项：

```bash
uv run issuedeck import-github-issues example/repo \
  --config server.toml \
  --project-key example \
  --kind feature \
  --state all \
  --status-map closed=done
```

私有仓库或更高限额可以设置 `GITHUB_TOKEN`，也可以传 `--github-token`。在
Dashboard 中打开项目后，也可以从侧边栏进入“导入 GitHub”，先预览再写入。详见
[GitHub Issues 导入](docs/github-issues-import.zh-CN.md)。

## Markdown 任务清单导入

从文件或目录导入普通 Markdown checkbox：

```bash
uv run issuedeck import-markdown-list TODO.md \
  --config server.toml \
  --project-key example \
  --kind feature \
  --tag planning
```

默认会跳过已勾选任务；加 `--include-checked` 可以把它们导入到第一个 terminal
status。详见 [Markdown 任务清单导入](docs/markdown-task-list-import.zh-CN.md)。

## CSV 导入

导入 tracker export 或表格里的任务行：

```bash
uv run issuedeck import-csv issues.csv \
  --config server.toml \
  --project-key example \
  --preset github \
  --status-map open=proposed \
  --status-map closed=done
```

自定义表头可以用 `--field-alias`，写入前建议先用 `--dry-run` 校验。详见
[CSV 导入](docs/csv-import.zh-CN.md)。

## JSON 导入

导入 JSON 数组，或 `{ "issues": [...] }` 这类带包装字段的 tracker export：

```bash
uv run issuedeck import-json issues.json \
  --config server.toml \
  --project-key example \
  --preset github \
  --status-map open=proposed \
  --status-map closed=done
```

自定义 key 可以用 `--field-alias`，写入前建议先用 `--dry-run` 校验。详见
[JSON 导入](docs/json-import.zh-CN.md)。

## 托管 Tracker 导出

GitHub Issues、Linear、Jira 和通用表格的导出方式见
[托管 Tracker 导出指南](docs/hosted-tracker-exports.zh-CN.md)。里面包含源工具导出命令，
以及对应的 `import-json` / `import-csv` 调用。

## MCP

客户端配置示例见 [MCP 客户端接入](docs/mcp-clients.zh-CN.md)。

MCP 进程通过 REST API 与 IssueDeck 通信，不直接访问 SQLite。`create_item` 和
`update_item` 可写入 `custom_fields`，`bulk_update_items` 可批量更新自定义字段，
`list_items` 可使用重复的 `custom_field` 筛选条件。环境变量：

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

首发传播文案见 [Launch Kit](docs/launch-kit.zh-CN.md)。
适合新贡献者认领的方向见 [Starter Issue Backlog](docs/launch-issues.md)。
维护者和后续 AI coding 窗口的提交规范见
[维护者工作流规范](docs/maintainer-workflow.zh-CN.md)。

## License

MIT. See [LICENSE](LICENSE).

路线图见 [ROADMAP.md](ROADMAP.md)。
PyPI Trusted Publishing 配置见 [docs/pypi-publishing.md](docs/pypi-publishing.md)。
