# Markdown 任务清单导入

[English](markdown-task-list-import.md)

`issuedeck import-markdown-list` 可以把普通 Markdown task list 转成 IssueDeck
item。它适合轻量的 `TODO.md`、GitHub issue 描述、发布计划和项目规划文件，这类
文件通常只有 checkbox 任务，没有 YAML frontmatter。

## 支持的语法

导入器会识别这些 task list 形式：

```markdown
- [ ] Add keyboard shortcut hints
- [x] Move old tracker data into IssueDeck
* [ ] Fix dashboard empty state
1. [ ] Review GitHub issue https://github.com/example/repo/issues/42
```

任务下面的缩进行会写入 item 正文：

```markdown
- [ ] Add export dry-run output
  Keep the wording short and include counts.
```

任务标题或备注里的 GitHub issue、PR、commit URL 会自动转成规范化 external link。

## 导入单个文件

```bash
uv run issuedeck import-markdown-list TODO.md \
  --config server.toml \
  --project-key example \
  --kind feature
```

默认会跳过已勾选任务，避免把已经完成的历史任务塞进活跃队列。加
`--include-checked` 后，已勾选任务会导入到项目配置里的第一个 terminal status。

```bash
uv run issuedeck import-markdown-list TODO.md \
  --config server.toml \
  --project-key example \
  --kind feature \
  --include-checked
```

## 导入目录

`source` 也可以指向目录，导入器会递归读取所有非隐藏的 `*.md` 文件：

```bash
uv run issuedeck import-markdown-list ./planning \
  --config server.toml \
  --project-key example \
  --kind improvement \
  --tag planning
```

建议先用 `--dry-run` 预览数量，不写入 SQLite：

```bash
uv run issuedeck import-markdown-list ./planning \
  --config server.toml \
  --project-key example \
  --dry-run
```

## 参数

- `--kind`：创建的 IssueDeck kind。省略时使用项目配置里的第一个 kind。
- `--tag`：给每个导入项增加 tag，可重复传入。导入器始终会加上 `markdown`。
- `--applies-to`：指定目标分支，可重复传入。省略时使用项目配置里的所有分支。
- `--include-checked`：把已勾选任务导入到第一个 terminal status。
- `--dry-run`：只打印导入摘要，不写入数据库。

如果 Markdown 文件已经有 YAML frontmatter 和显式 ID，请使用更严格的
[Markdown Frontmatter Import](markdown-frontmatter-import.zh-CN.md)。
