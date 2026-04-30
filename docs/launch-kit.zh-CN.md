# IssueDeck 首发传播包

公开分享 IssueDeck 到 GitHub、X/Twitter、Hacker News、Reddit、Discord 或技术社区时，
可以直接复用这里的文案。

## GitHub 项目页

建议仓库描述：

> 面向人和 AI coding agent 的本地优先 issue deck：Dashboard、MCP tools、
> SQLite，以及 CSV/JSON/Markdown 导入。

建议 topics：

```text
issue-tracker, mcp, ai-agents, coding-agents, fastapi, sqlite, self-hosted,
local-first, developer-tools, project-management
```

建议社交预览图：

```text
docs/assets/issuedeck-social-preview.png
```

主要 demo 动图：

```text
docs/assets/issuedeck-demo.gif
```

## 一句话介绍

IssueDeck 是一个本地优先、自托管的事项看板，面向小团队和 AI coding agent。
人使用 Dashboard，agent 使用 MCP tools，事项数据统一放在 FastAPI + SQLite
服务里，不再散落在多个 Markdown 文件中。

标语：

> 比 Jira 更轻，比 Markdown 更稳。

试用：

```bash
uvx issuedeck demo --open
```

## 社交平台短文案

我发布了 IssueDeck。

它是一个面向小团队和 AI coding 工作流的本地优先事项看板：

- 给人用的 Web Dashboard
- 给 coding agent 用的 MCP tools
- SQLite 本地存储
- CSV/JSON/Markdown 导入
- 默认假数据 demo，适合公开截图
- Docker/GHCR 镜像发布
- 签名生命周期 Webhooks

直接试用：

```bash
uvx issuedeck demo --open
```

Repo: https://github.com/xq520mmy/IssueDeck

## 功能要点

- 给人使用的 Web Dashboard。
- 给 coding agent 使用的 MCP tools。
- SQLite 本地存储，多项目配置。
- CSV、JSON、Markdown task-list 和 Markdown frontmatter 导入。
- GitHub issue、PR、commit external link。
- 签名生命周期 Webhooks，方便下游自动化。
- Docker/GHCR 镜像和 PyPI/uvx 安装路径。
- 默认假数据 demo，适合公开截图。

## 30 秒 Demo 脚本

1. 运行 `uvx issuedeck demo --open`。
2. 用 `issuedeck-local-token` 登录。
3. 打开 list 和 kanban 视图。
4. 新建一个假 item，并附加 GitHub URL。
5. 展示搜索、item detail 和 activity timeline。

如果要体验还没发版的 `main` 分支：

```bash
uvx --from git+https://github.com/xq520mmy/IssueDeck issuedeck demo --open
```

## 技术社区长一点的版本

IssueDeck 是我做的一个本地优先 issue tracker，定位是小团队和 AI coding
agent 共用的轻量工作台。

我做它的原因是：Markdown tracker 很方便，但当多个项目、agent、release、链接和
搜索都需要同一个可信来源时，纯 Markdown 很快会变得松散。

IssueDeck 用 FastAPI + SQLite 跑一个小服务。人用 Dashboard，coding agent 通过
MCP tools 访问同一套 REST API。现在已经支持多项目配置、全文搜索、事项关系、
Activity Timeline、Ship 记录、CSV/JSON/Markdown 导入、Markdown 导出、
scoped tokens、Docker 部署和签名生命周期 Webhooks。

默认 demo 使用假数据：

```bash
uvx issuedeck demo --open
```

如果想试还没发布的 `main` 分支，可以使用 `uvx --from git+...`。

## 常用链接

- 仓库：https://github.com/xq520mmy/IssueDeck
- PyPI：https://pypi.org/project/issuedeck/
- 最新 release：https://github.com/xq520mmy/IssueDeck/releases/latest
- 截图画廊：https://github.com/xq520mmy/IssueDeck/blob/main/docs/gallery.zh-CN.md
- Demo 动图：https://github.com/xq520mmy/IssueDeck/blob/main/docs/assets/issuedeck-demo.gif
- 路线图：https://github.com/xq520mmy/IssueDeck/blob/main/ROADMAP.md
- 新贡献者任务：https://github.com/xq520mmy/IssueDeck/blob/main/docs/launch-issues.md
- CSV 导入：https://github.com/xq520mmy/IssueDeck/blob/main/docs/csv-import.zh-CN.md
- JSON 导入：https://github.com/xq520mmy/IssueDeck/blob/main/docs/json-import.zh-CN.md
- 托管 tracker 导出：https://github.com/xq520mmy/IssueDeck/blob/main/docs/hosted-tracker-exports.zh-CN.md
