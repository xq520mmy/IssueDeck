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

Mappable IssueDeck fields are `id`, `kind`, `status`, `title`, `tags`, and
`applies_to`.
