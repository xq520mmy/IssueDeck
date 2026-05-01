# GitHub URL 导入

[English](github-import.md)

`issuedeck import-github-url` 可以从 GitHub issue、pull request 或 commit URL
创建 IssueDeck item。它不是同步引擎：不会调用 GitHub API，不会同步评论，也不会持续
更新状态。它只创建一个本地 item，并写入规范化的 external link，方便把 GitHub 上的
工作纳入 IssueDeck 跟踪。

如果要通过 GitHub API 批量导入整个仓库的 issues，请使用
[`import-github-issues`](github-issues-import.zh-CN.md)。

## 创建 Item

```bash
uv run issuedeck import-github-url \
  --config server.toml \
  --project-key example \
  --kind feature \
  https://github.com/example/repo/issues/42
```

命令会推断：

- `github_issue`、`github_pr` 或 `github_commit`
- 去掉 query 参数后的稳定 GitHub URL
- 默认标题，例如 `Review GitHub issue #42 from example/repo`
- 默认 `github` tag
- 指向源 URL 的默认正文

## 先预览

加 `--dry-run` 可以只打印 create payload，不写入 SQLite：

```bash
uv run issuedeck import-github-url \
  --config server.toml \
  --project-key example \
  --kind bug \
  --dry-run \
  https://github.com/example/repo/issues/42
```

## 参数

- `--kind`：要创建的 IssueDeck kind。省略时使用项目配置中的第一个 kind。
- `--title`：覆盖自动生成的标题。
- `--body`：覆盖自动生成的正文。
- `--tag`：增加 tag，可重复传入。
- `--applies-to`：指定目标分支，可重复传入。
- `--link-label`：覆盖 external link label。

## 示例

Pull request：

```bash
uv run issuedeck import-github-url \
  --config server.toml \
  --project-key example \
  --kind improvement \
  --tag upstream \
  https://github.com/example/repo/pull/7
```

Commit：

```bash
uv run issuedeck import-github-url \
  --config server.toml \
  --project-key example \
  --kind feature \
  --title "Review upstream fix" \
  https://github.com/example/repo/commit/abc1234def
```

## 适用场景

当 GitHub 上已经有 issue 或 PR，而你希望在 IssueDeck 里建立一个本地跟踪项时，用
这个 helper 就够了。完整 issue 镜像、label 同步、评论导入等能力应该作为独立集成层。
