# 托管 Tracker 导出指南

[English](hosted-tracker-exports.md)

小规模迁移不一定需要完整同步引擎。先从源工具导出文件，用 `--dry-run` 校验，
确认无误后再把行写入本地 IssueDeck 项目。

## GitHub Issues

使用 GitHub CLI：

```bash
gh issue list \
  --repo OWNER/REPO \
  --state all \
  --limit 1000 \
  --json number,title,state,labels,url,body \
  > github-issues.json
```

导入 IssueDeck：

```bash
uv run issuedeck import-json github-issues.json \
  --config server.toml \
  --project-key example \
  --preset github \
  --status-map OPEN=proposed \
  --status-map CLOSED=done \
  --dry-run
```

确认数量和状态映射无误后，去掉 `--dry-run` 即可写入。

## Linear

在 Linear 的 workspace settings 或对应 team view 中导出 issues CSV，然后导入：

```bash
uv run issuedeck import-csv linear-issues.csv \
  --config server.toml \
  --project-key example \
  --preset linear \
  --status-map Backlog=proposed \
  --status-map Todo=proposed \
  --status-map "In Progress=in_progress" \
  --status-map Done=done \
  --dry-run
```

如果 Linear 里使用了自定义 workflow 名称，请继续追加 `--status-map SOURCE=TARGET`。

## Jira

在 Jira 中筛选要迁移的 issues，然后使用 **Export CSV**。`jira` preset 会识别常见字段，
例如 `Summary`、`Description`、`Issue Type`、`Status`、`Labels`、
`Fix Version/s`、`Key` 和 URL 类字段。

```bash
uv run issuedeck import-csv jira-issues.csv \
  --config server.toml \
  --project-key example \
  --preset jira \
  --status-map "To Do=proposed" \
  --status-map "In Progress=in_progress" \
  --status-map Done=done \
  --dry-run
```

## 通用表格

Airtable、Notion、Google Sheets 或手工维护的表格可以导出 CSV，并用自定义别名匹配表头：

```bash
uv run issuedeck import-csv backlog.csv \
  --config server.toml \
  --project-key example \
  --preset generic \
  --field-alias title=Issue \
  --field-alias body=Notes \
  --field-alias status=Stage \
  --field-alias tags=Tags \
  --dry-run
```

## 写入前检查

- 先运行 `--dry-run`。
- 确认源状态映射到了真实的 IssueDeck status。
- 确认分支名和项目配置一致；如果不需要逐行指定分支，可以省略分支列，默认使用所有项目分支。
- 在检查完导入结果前，保留原始导出文件。
