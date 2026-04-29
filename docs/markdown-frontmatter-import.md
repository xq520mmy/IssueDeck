# Markdown Frontmatter Import

IssueDeck imports Markdown issue collections from a directory shaped like this:

```text
markdown-tracker/
  items/
    FEAT-0001.md
    BUG-0002.md
    .archive/
      FEAT-0003.md
```

Each file uses YAML frontmatter followed by the item body.

## Accepted Schema

Required fields:

| IssueDeck field | Accepted frontmatter keys | Notes |
| --- | --- | --- |
| `id` | `id` | Must be unique inside the import bundle. |
| `kind` | `kind`, `type` | Value must match a kind in the project config. |
| `status` | `status`, `state` | Value must match a status in the project config. |
| `title` | `title` | Stored as the item title. |

Optional fields:

| IssueDeck field | Accepted frontmatter keys | Notes |
| --- | --- | --- |
| `tags` | `tags`, `labels` | YAML list or comma-separated string. |
| `applies_to` | `applies_to` | YAML list or scalar branch key. Values must match project branches. |
| `created_at` | `created_at` | ISO timestamp; defaults to import time. |
| `updated_at` | `updated_at` | ISO timestamp; defaults to import time. |
| `deleted_at` | `deleted_at` | Used for files imported from `items/.archive/`; defaults to import time. |
| `external_links` | `external_links` | URL string, YAML list, or objects with `url`, `label`, and `link_type`. GitHub URLs are normalized automatically. |
| ship record | `shipped_in_v3`, `shipped_in_v2` | Creates ship records for the built-in branch keys. |
| ship commits | `commits_v3`, `commits_v2` | YAML list or comma-separated string. |

Example:

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

Markdown body goes here.
```

## Field Aliases

The importer accepts common aliases by default:

- `type` maps to `kind`
- `state` maps to `status`
- `labels` maps to `tags`

For other tracker schemas, add aliases with `--field-alias`. Aliases are added
to the default schema rather than replacing it.

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

Mappable IssueDeck fields are `id`, `kind`, `status`, `title`, `tags`,
`applies_to`, and `external_links`.

## Adapter Presets

Presets add common aliases before any custom `--field-alias` options. They do
not change validation: imported kinds, statuses, and branches still need to
match your project config.

```bash
uv run issuedeck migrate \
  --config server.toml \
  --from-frontmatter /path/to/markdown-tracker \
  --project-key myproject \
  --preset github
```

Available presets:

| Preset | Useful for | Added aliases |
| --- | --- | --- |
| `github` | GitHub issue exports or issue-like Markdown | `number`, `issue_number`, `html_url`, `url` |
| `linear` | Linear-style Markdown exports | `identifier`, `issue_id`, `workflow_state`, `label_names`, `branch`, `links`, `attachments` |
| `generic` | Older custom Markdown trackers | `key`, `local_id`, `category`, `workflow`, `keywords`, `branch`, `branches`, `links`, `refs`, `references` |

You can combine a preset with explicit aliases:

```bash
uv run issuedeck migrate \
  --config server.toml \
  --from-frontmatter /path/to/markdown-tracker \
  --project-key myproject \
  --preset linear \
  --field-alias status=phase
```
