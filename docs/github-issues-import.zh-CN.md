# GitHub Issues 导入

[English](github-issues-import.md)

`issuedeck import-github-issues` 会通过 GitHub REST API 从仓库导入 issues。
它是轻量导入，不是双向同步：会创建本地 IssueDeck item，写入规范化的 GitHub
external link，重复运行时跳过已经导入过的 issue，不会镜像评论或持续同步状态。

## 导入 Open Issues

```bash
uv run issuedeck import-github-issues example/repo \
  --config server.toml \
  --project-key example \
  --kind feature
```

仓库参数可以是 `owner/repo`，也可以是完整 URL，例如
`https://github.com/example/repo`。

## 认证

公开仓库可以不传 token，但认证请求有更高限额，也能访问私有仓库。

```bash
export GITHUB_TOKEN="ghp_..."
uv run issuedeck import-github-issues example/private-repo \
  --config server.toml \
  --project-key example
```

PowerShell：

```powershell
$env:GITHUB_TOKEN = "ghp_..."
uv run issuedeck import-github-issues example/private-repo `
  --config server.toml `
  --project-key example
```

也可以用 `--github-token` 只给当前命令传 token。

## 可重复运行

导入器会检查同一个项目里已有的 external links，并跳过已经存在的 GitHub issue URL。
因此同一个仓库可以重复导入，只会补新增 issue。

```bash
uv run issuedeck import-github-issues example/repo \
  --config server.toml \
  --project-key example \
  --state all \
  --status-map open=proposed \
  --status-map closed=done \
  --limit 100
```

## 过滤参数

- `--state open|closed|all`：要拉取的 GitHub issue 状态，默认 `open`。
- `--label bug`：只拉取带某个 label 的 issue，可重复传入。
- `--since 2026-01-01T00:00:00Z`：只拉取此时间之后更新的 issue。
- `--limit 50`：最多导入多少条，默认 `50`。
- `--include-pulls`：同时导入 GitHub issues endpoint 返回的 pull requests。

默认会跳过 PR，因为 GitHub issues endpoint 会把 PR 也返回出来，并用
`pull_request` 字段标记。

## 映射规则

- GitHub issue title 会成为 IssueDeck title。
- GitHub issue body 会写入 IssueDeck body，并追加来源信息。
- GitHub labels 会成为 IssueDeck tags，另外默认加上 `github` tag。
- GitHub state 会映射到项目状态。默认 `open` 映射到第一个非终态状态，`closed`
  映射到第一个终态状态；也可以用 `--status-map` 覆盖。

只预览不写入：

```bash
uv run issuedeck import-github-issues example/repo \
  --config server.toml \
  --project-key example \
  --dry-run
```

