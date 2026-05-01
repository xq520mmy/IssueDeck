# JSON 导入

[English](json-import.md)

`issuedeck import-json` 可以把 JSON tracker export 转成 IssueDeck item。它支持
顶层数组、单个 JSON object，也支持常见包装结构，例如 `{"items": [...]}`、
`{"issues": [...]}`、`{"data": [...]}`、`{"records": [...]}` 和
`{"tasks": [...]}`。

同一套 JSON 映射流程也可以在 Dashboard 里通过
[Dashboard 文件导入](dashboard-file-imports.zh-CN.md) 使用。

## 导入文件

```bash
uv run issuedeck import-json issues.json \
  --config server.toml \
  --project-key example \
  --kind feature \
  --tag imported
```

建议先用 `--dry-run` 校验字段、状态、分支和数量，不写入 SQLite：

```bash
uv run issuedeck import-json issues.json \
  --config server.toml \
  --project-key example \
  --dry-run
```

## 支持的结构

顶层数组：

```json
[
  {
    "title": "Fix login redirect",
    "state": "open",
    "labels": ["bug", "auth"],
    "html_url": "https://github.com/example/repo/issues/42"
  }
]
```

带包装字段的 export：

```json
{
  "issues": [
    {
      "title": "Ship keyboard flow",
      "state": "In Progress",
      "labels": [{"name": "ux"}],
      "html_url": "https://github.com/example/repo/pull/7"
    }
  ]
}
```

## 字段

字段匹配不区分大小写，也会把空格、短横线和下划线视为等价。

- `title`、`summary`、`name`：item 标题，必填。
- `body`、`description`、`notes`、`details`：item 正文。
- `kind`、`type`、`category`、`issue_type`：item kind。为空时使用 `--kind`。
- `status`、`state`、`workflow`、`workflow_state`：item status。为空时使用项目里第一个非 terminal status。
- `tags`、`labels`、`keywords`、`label_names`：tag。支持字符串数组，也支持带 `name`、`label`、`value`、`title` 或 `key` 的对象数组。
- `applies_to`、`branch`、`branches`、`fix_version`：目标分支。
- `external_links`、`links`、`refs`、`references`、`url`、`html_url`：来源链接。GitHub issue、PR 和 commit URL 会自动规范化。
- `source_id`、`id`、`key`、`identifier`、`issue_key`、`number`：源 tracker ID，会写入 item 正文。

## Preset 和状态映射

常见 tracker export 可以使用 preset：

```bash
uv run issuedeck import-json github-issues.json \
  --config server.toml \
  --project-key example \
  --preset github \
  --status-map open=proposed \
  --status-map closed=done
```

可用 preset 是 `github`、`linear`、`jira` 和 `generic`。

自定义 JSON key 可以用 `--field-alias`，源工作流状态和项目配置不一致时用
`--status-map`。遇到未知 status 时，导入会在写入任何数据前失败。
