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

## Dashboard

事项创建/编辑表单会自动渲染配置好的自定义字段，提交后的值会展示在事项详情页。

## 当前范围

自定义字段现在会被存储和导出，但还不能在列表视图中搜索、筛选，也暂未从
CSV/JSON/Markdown 导入源自动映射。
