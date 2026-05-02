# 自定义字段

项目可以定义轻量自定义字段，用来记录 priority、estimate、客户影响、来源 URL
等额外元数据。字段值会随事项一起存储，通过 REST API 返回，在 Dashboard 展示，
并进入 Markdown 导出和审计导出包。

## 配置

在项目 TOML 中加入 `[custom_fields.<key>]`：

```toml
[custom_fields.priority]
label = "Priority"
type = "select"
required = true
options = ["low", "medium", "high"]

[custom_fields.estimate]
label = "Estimate"
type = "number"

[custom_fields.customer_impact]
label = "Customer impact"
type = "checkbox"

[custom_fields.source_url]
label = "Source URL"
type = "url"
```

字段 key 必须以小写字母开头，可包含小写字母、数字、`-` 或 `_`。

支持的字段类型：

- `text`
- `number`
- `checkbox`
- `select`
- `url`

`select` 字段必须定义 `options`。通过 API 创建或更新事项时，必填字段必须有值。

## API

创建或更新事项时可以传 `custom_fields`：

```json
{
  "kind": "feature",
  "title": "Add onboarding report",
  "custom_fields": {
    "priority": "high",
    "estimate": 3,
    "customer_impact": true
  }
}
```

未知字段、非法 select 选项、非数字 number 值都会返回 `invalid_custom_field`。

批量更新可以一次为多个事项设置自定义字段：

```json
{
  "local_ids": ["FEAT-0001", "FEAT-0002"],
  "custom_fields": {
    "priority": "high",
    "customer_impact": true
  }
}
```

列表 API 可以通过重复的 `custom_field=FIELD=VALUE` 查询参数筛选自定义字段：

```bash
curl \
  -H "Authorization: Bearer $ISSUEDECK_API_TOKEN" \
  "http://127.0.0.1:8775/api/v1/projects/example/items?custom_field=priority=high"
```

精确筛选使用 `FIELD=VALUE`。数字字段还支持 `estimate>=3`、`estimate<=8`
这类范围筛选；文本、URL 和数字字段支持 `FIELD:*`、`FIELD:present`、
`FIELD:missing` 这类有值/缺失筛选。Dashboard 列表筛选和保存筛选也支持这些条件。

## Dashboard

事项创建/编辑表单会自动渲染配置好的自定义字段，提交后的值会展示在列表摘要和
事项详情页。列表筛选面板也会渲染配置好的自定义字段，因此保存筛选可以包含
`priority=high` 或 `customer_impact=true` 这类条件。列表批量操作区也可以为所有
选中事项设置自定义字段；留空表示保持原值不变。

## 导入

CSV 和 JSON 导入可以通过 `custom.<field_key>=alias` 字段别名，把来源列或对象
字段映射到项目自定义字段：

```bash
uv run issuedeck import-csv backlog.csv \
  --config server.toml \
  --project-key example \
  --field-alias custom.priority=Priority \
  --field-alias custom.estimate=Points
```

Dashboard 文件导入表单也支持同样的别名语法。Markdown 任务列表没有结构化字段，
因此不会映射自定义字段。
