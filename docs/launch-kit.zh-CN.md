# IssueDeck 首发传播包

公开分享 IssueDeck 第一个版本时可以直接复用这里的文案。

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

我发布了 IssueDeck v0.3.2。

它是一个面向小团队和 AI coding 工作流的本地优先事项看板：

- 给人用的 Web Dashboard
- 给 coding agent 用的 MCP tools
- SQLite 本地存储
- 默认假数据 demo，适合公开截图
- Docker/GHCR 镜像发布
- 签名生命周期 Webhooks

直接试用：

```bash
uvx issuedeck demo --open
```

Repo: https://github.com/xq520mmy/IssueDeck

## 技术社区长一点的版本

IssueDeck 是我做的一个本地优先 issue tracker，定位是小团队和 AI coding
agent 共用的轻量工作台。

我做它的原因是：Markdown tracker 很方便，但当多个项目、agent、release、链接和
搜索都需要同一个可信来源时，纯 Markdown 很快会变得松散。

IssueDeck 用 FastAPI + SQLite 跑一个小服务。人用 Dashboard，coding agent 通过
MCP tools 访问同一套 REST API。现在已经支持多项目配置、全文搜索、事项关系、
Activity Timeline、Ship 记录、Markdown 导入导出、scoped tokens、Docker 部署和
签名生命周期 Webhooks。

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
- 路线图：https://github.com/xq520mmy/IssueDeck/blob/main/ROADMAP.md
- 新贡献者任务：https://github.com/xq520mmy/IssueDeck/blob/main/docs/launch-issues.md
