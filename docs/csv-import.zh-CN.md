# CSV 导入

[English](csv-import.md)

`issuedeck import-csv` 可以把 tracker 导出的 CSV 或表格里的任务行转成
IssueDeck item。它适合从 GitHub Issues、Linear、Jira、Airtable、Notion 表格，
以及手工维护的 CSV 做轻量迁移。

同一套 CSV 映射流程也可以在 Dashboard 里通过
[Dashboard 文件导入](dashboard-file-imports.zh-CN.md) 使用。

## 导入文件

```bash
uv run issuedeck import-csv issues.csv \
  --config server.toml \
  --project-key example \
  --kind feature \
  --tag imported
```

建议先用 `--dry-run` 校验列名、状态、分支和数量，不写入 SQLite：

```bash
uv run issuedeck import-csv issues.csv \
  --config server.toml \
  --project-key example \
  --dry-run
```

## 列名

列名匹配不区分大小写，也会把空格、短横线和下划线视为等价。例如 `Issue Type`、
`issue_type` 和 `issue-type` 会匹配同一个别名。

导入器默认识别这些常见列：

- `title`、`summary`、`name`：item 标题，必填。
- `body`、`description`、`notes`、`details`：item 正文。
- `kind`、`type`、`category`、`issue_type`：item kind。为空时使用 `--kind`。
- `status`、`state`、`workflow`、`workflow_state`：item status。为空时使用项目里第一个非 terminal status。
- `tags`、`labels`、`keywords`、`label_names`：tag，支持逗号、分号、竖线或换行分隔。
- `applies_to`、`branch`、`branches`、`fix_version`：目标分支。为空时使用所有项目分支，除非传入 `--applies-to`。
- `external_links`、`links`、`refs`、`references`、`url`、`html_url`：来源链接。GitHub issue、PR 和 commit URL 会自动规范化。
- `source_id`、`id`、`key`、`identifier`、`issue_key`、`number`：源 tracker ID，会写入 item 正文。

## Preset

可以为常见 tracker 导出格式启用别名 preset：

```bash
uv run issuedeck import-csv github-issues.csv \
  --config server.toml \
  --project-key example \
  --preset github \
  --status-map open=proposed \
  --status-map closed=done
```

可用 preset：

- `github`
- `linear`
- `jira`
- `generic`

## 自定义别名

如果你的 CSV 表头不同，可以用 `--field-alias` 补充：

```bash
uv run issuedeck import-csv backlog.csv \
  --config server.toml \
  --project-key example \
  --kind improvement \
  --field-alias title=Issue \
  --field-alias body=Long Description \
  --field-alias status=Workflow
```

可映射字段包括 `title`、`body`、`kind`、`status`、`tags`、`applies_to`、
`external_links`、`source_id` 和 `source_url`。

项目自定义字段使用 `custom.<field_key>` 前缀：

```bash
uv run issuedeck import-csv backlog.csv \
  --config server.toml \
  --project-key example \
  --field-alias custom.priority=Priority \
  --field-alias custom.estimate=Points
```

导入写入前会按照项目配置校验自定义字段，因此必填字段、select 选项、数字和
checkbox 与 API 创建事项时保持一致。

## 状态映射

IssueDeck 会用项目配置校验导入后的 status。`open`、`closed`、`in progress`
这类常见状态会尽量自动映射，但真实迁移时建议显式指定：

```bash
uv run issuedeck import-csv jira.csv \
  --config server.toml \
  --project-key example \
  --preset jira \
  --status-map "To Do=proposed" \
  --status-map "In Progress=in_progress" \
  --status-map Done=done
```

遇到未知 status 时，导入会在写入任何数据前失败。
