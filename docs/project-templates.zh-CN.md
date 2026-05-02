# 项目模板

IssueDeck 可以在 Dashboard 里基于起步模板创建新项目配置。打开
`/dashboard/projects-new`，填写项目键和项目名称，然后选择模板并提交。

模板会写入普通的 `projects/<key>.toml` 文件。创建之后，你仍然可以直接编辑
TOML 来重命名类型、添加状态、修改 ID 前缀，或添加发布分支。

## 本地模板包

如果想在不修改 IssueDeck 源码的情况下增加模板，可以把 TOML 文件放进
`server.toml` 里的 `project_templates_dir`：

```toml
project_templates_dir = "./project-templates"
```

每个 `*.toml` 文件描述一个起步模板：

```toml
key = "support"
name = "Support queue"
description = "Customer support triage with escalation states."
ship_exempt_kinds = ["question"]

[custom_fields.priority]
label = "Priority"
type = "select"
options = ["low", "high"]

[[kinds]]
key = "question"
label = "Question"
prefix = "QST"

[[kinds]]
key = "incident"
label = "Incident"
prefix = "INC"

[[statuses]]
key = "new"
label = "New"

[[statuses]]
key = "investigating"
label = "Investigating"

[[statuses]]
key = "resolved"
label = "Resolved"
terminal = true

[[branches]]
key = "support"
label = "Support"
```

自定义模板 key 不能和内置模板重复。如果某个状态设置了 `requires_ship = true`，
模板必须至少定义一个分支。本地模板包也可以包含项目 `custom_fields`。这些模板
可能包含团队私有流程名称，因此默认 `.gitignore` 会忽略
`project-templates/*.toml`，只有你明确准备公开的示例才需要提交。

## 内置模板

| 模板 | 适合场景 | 包含内容 |
| --- | --- | --- |
| 基础事项看板 | Demo 和轻量个人 backlog | Feature、Bug、Improvement；Proposed、In Progress、Done、Won't Fix；Main 分支 |
| Agent 工作流 | 人和 AI coding agent 协同分诊 | Feature、Bug、Improvement、Task；Proposed、In Progress、Blocked、Ready to Ship、Done、Won't Fix；Main 分支 |
| 软件团队 | 更完整的产品交付看板 | Epic、Feature、Bug、Chore；Backlog、Ready、In Progress、Review、Done、Won't Fix；Main 和 Release 分支 |

## 注意事项

- 项目键必须是小写且适合放在 URL 中，例如 `acme-web`。
- 模板只影响初始 TOML。后续切换模板不会改写已有项目。
- 带有 `requires_ship = true` 的状态仍然遵循 IssueDeck 的发布规则。
