# Dashboard 文件导入

[English](dashboard-file-imports.md)

Dashboard 可以直接导入 CSV、JSON 和 Markdown 任务列表文件，不需要切到 CLI。

打开项目后，从侧边栏进入 **导入文件**，上传文件并先运行 **预览导入**。预览会解析
文件，并应用字段别名、状态映射、预设、标签和目标分支，但不会写入事项。

确认预览结果后再点 **导入事项**。成功导入会给本次写入的事项自动添加唯一的
`csv-import-*`、`json-import-*` 或 `markdown-import-*` 批次标签。结果面板会直接
链接到按批次标签筛选后的列表，方便立刻批量分诊新事项。

成功写入至少一个事项的导入也会进入
[Dashboard 导入历史](dashboard-import-history.zh-CN.md)，之后可以重新打开同一批次。

## 支持格式

- CSV tracker export 和表格文件，使用与 [`import-csv`](csv-import.zh-CN.md) 相同的
  映射规则。
- JSON 数组或 `{ "issues": [...] }` 这类包裹格式，使用与
  [`import-json`](json-import.zh-CN.md) 相同的映射规则。
- GitHub 风格 Markdown task list，使用与
  [`import-markdown-list`](markdown-task-list-import.zh-CN.md) 相同的解析规则。

## CSV 和 JSON 选项

- `预设`: 常见导出格式的字段别名。支持 `github`、`jira`、`linear` 和 `generic`。
- `字段别名`: 每行一个 `FIELD=alias[,alias...]`。支持字段包括 `title`、`body`、
  `kind`、`status`、`tags`、`applies_to`、`external_links`、`source_id` 和
  `source_url`。项目自定义字段使用 `custom.<field_key>=alias`，例如
  `custom.priority=Priority`。
- `状态映射`: 每行一个 `SOURCE=TARGET`，例如 `closed=done`。

## Markdown 选项

Markdown 导入默认跳过已勾选任务。开启 **包含已勾选的 Markdown 任务** 后，会把它们
导入到项目中的第一个终态状态。
