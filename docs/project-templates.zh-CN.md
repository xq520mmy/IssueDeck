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

公开或分享模板包之前，可以先本地校验：

```bash
issuedeck validate-project-templates ./project-templates
issuedeck validate-project-templates ./project-templates --format json
```

这个命令会检查每个 `*.toml` 文件，并汇总所有错误，不会在第一个失败文件处停止。
只要有模板需要修复，命令就会以退出码 `2` 结束。省略目录参数时，IssueDeck 会从
`server.toml` 读取 `project_templates_dir`。

## 示例模板包

IssueDeck 内置了几个可以直接安装的示例模板包，覆盖常见工作流：

| 示例 | 适合场景 | 亮点 |
| --- | --- | --- |
| `support` | 客服队列和事故跟进 | Question、Incident、Request、SLA 风险、客户、来源链接 |
| `content` | 内容日历和编辑排期 | Idea、Draft、Asset、发布渠道、发布时间窗口 |
| `research` | 调研、实验和验证工作 | Question、Experiment、Finding、Decision、信心等级、投入量 |

查看可用示例：

```bash
issuedeck list-project-template-examples
issuedeck list-project-template-examples --format json
```

把某个示例安装到本地模板包目录：

```bash
issuedeck install-project-template-example support --config server.toml
issuedeck install-project-template-example research \
  --templates-dir ./project-templates
```

可以用 `--dry-run` 先预览将要写入的 TOML；如果示例文件已经存在，可以用
`--force` 覆盖。安装完成后，这些示例会出现在
`issuedeck list-project-templates` 和 Dashboard 的新建项目表单里。
Dashboard 的新建项目页也可以直接安装这些示例。

## 把项目导出为模板

当你在 `projects/<key>.toml` 里调好一套工作流之后，可以把它导出成可复用的模板包：

```bash
issuedeck export-project-template myapp --config server.toml
issuedeck export-project-template myapp \
  --config server.toml \
  --template-key team-delivery \
  --name "Team delivery" \
  --out ./project-templates/team-delivery.toml
```

这个命令会把项目的类型、状态、分支、发布豁免规则和自定义字段复制到本地模板包格式。
可以用 `--dry-run` 预览 TOML，用 `--force` 覆盖已有输出文件。

## 内置模板

| 模板 | 适合场景 | 包含内容 | 自定义字段 |
| --- | --- | --- | --- |
| 基础事项看板 | Demo 和轻量个人 backlog | Feature、Bug、Improvement；Proposed、In Progress、Done、Won't Fix；Main 分支 | Priority、Source URL |
| Agent 工作流 | 人和 AI coding agent 协同分诊 | Feature、Bug、Improvement、Task；Proposed、In Progress、Blocked、Ready to Ship、Done、Won't Fix；Main 分支 | Priority、Estimate、Customer impact、Source URL |
| 软件团队 | 更完整的产品交付看板 | Epic、Feature、Bug、Chore；Backlog、Ready、In Progress、Review、Done、Won't Fix；Main 和 Release 分支 | Priority、Estimate、Component、Source URL |

## 注意事项

- 项目键必须是小写且适合放在 URL 中，例如 `acme-web`。
- 模板只影响初始 TOML。后续切换模板不会改写已有项目。
- 带有 `requires_ship = true` 的状态仍然遵循 IssueDeck 的发布规则。
