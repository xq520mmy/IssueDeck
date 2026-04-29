# Markdown Frontmatter 导入

IssueDeck 可以从下面这种目录导入 Markdown 事项集合：

```text
markdown-tracker/
  items/
    FEAT-0001.md
    BUG-0002.md
    .archive/
      FEAT-0003.md
```

每个文件由 YAML frontmatter 和正文组成。

## 支持的字段

必填字段：

| IssueDeck 字段 | 支持的 frontmatter key | 说明 |
| --- | --- | --- |
| `id` | `id` | 在本次导入目录内必须唯一。 |
| `kind` | `kind`, `type` | 值必须匹配项目配置里的事项类型。 |
| `status` | `status`, `state` | 值必须匹配项目配置里的状态。 |
| `title` | `title` | 写入事项标题。 |

可选字段：

| IssueDeck 字段 | 支持的 frontmatter key | 说明 |
| --- | --- | --- |
| `tags` | `tags`, `labels` | YAML 列表或逗号分隔字符串。 |
| `applies_to` | `applies_to` | YAML 列表或单个分支 key，值必须匹配项目分支。 |
| `created_at` | `created_at` | ISO 时间；缺省为导入时间。 |
| `updated_at` | `updated_at` | ISO 时间；缺省为导入时间。 |
| `deleted_at` | `deleted_at` | 导入 `items/.archive/` 中的文件时使用；缺省为导入时间。 |
| `external_links` | `external_links` | URL 字符串、YAML 列表，或包含 `url`、`label`、`link_type` 的对象。GitHub URL 会自动规范化。 |
| ship 记录 | `shipped_in_v3`, `shipped_in_v2` | 为内置分支 key 创建发布记录。 |
| ship commits | `commits_v3`, `commits_v2` | YAML 列表或逗号分隔字符串。 |

示例：

```markdown
---
id: FEAT-0001
kind: feature
status: done
title: Add saved filters
tags: [dashboard, workflow]
applies_to: [v3]
shipped_in_v3: "0.2.0"
commits_v3: [abc123, def456]
external_links:
  - https://github.com/example/repo/pull/42
created_at: "2026-04-01T00:00:00+00:00"
updated_at: "2026-04-02T00:00:00+00:00"
---

这里是 Markdown 正文。
```

## 字段别名

导入器默认支持常见别名：

- `type` 映射到 `kind`
- `state` 映射到 `status`
- `labels` 映射到 `tags`

如果旧 tracker 使用了其他字段名，可以用 `--field-alias` 增加别名。别名会追加到
默认 schema，不会替换原有字段。

```bash
uv run issuedeck migrate \
  --config server.toml \
  --from-frontmatter /path/to/markdown-tracker \
  --project-key myproject \
  --field-alias kind=category,issue_type \
  --field-alias status=workflow \
  --field-alias tags=keywords \
  --field-alias applies_to=branches
```

可映射字段包括 `id`、`kind`、`status`、`title`、`tags`、`applies_to`
和 `external_links`。

## 适配器预设

预设会在自定义 `--field-alias` 之前追加一组常见别名。预设不会放宽校验：
导入后的 kind、status 和 branch 仍然必须匹配项目配置。

```bash
uv run issuedeck migrate \
  --config server.toml \
  --from-frontmatter /path/to/markdown-tracker \
  --project-key myproject \
  --preset github
```

可用预设：

| 预设 | 适用场景 | 追加别名 |
| --- | --- | --- |
| `github` | GitHub issue 导出或类似 issue 的 Markdown | `number`, `issue_number`, `html_url`, `url` |
| `linear` | 类 Linear 的 Markdown 导出 | `identifier`, `issue_id`, `workflow_state`, `label_names`, `branch`, `links`, `attachments` |
| `generic` | 旧的自定义 Markdown tracker | `key`, `local_id`, `category`, `workflow`, `keywords`, `branch`, `branches`, `links`, `refs`, `references` |

预设可以和显式别名一起使用：

```bash
uv run issuedeck migrate \
  --config server.toml \
  --from-frontmatter /path/to/markdown-tracker \
  --project-key myproject \
  --preset linear \
  --field-alias status=phase
```
