# JSON Import

[简体中文](json-import.zh-CN.md)

`issuedeck import-json` turns JSON tracker exports into IssueDeck items. It
accepts top-level arrays, a single JSON object, or wrapped exports such as
`{"items": [...]}`, `{"issues": [...]}`, `{"data": [...]}`, `{"records": [...]}`,
and `{"tasks": [...]}`.

The same JSON mapping flow is available in the dashboard through
[Dashboard File Imports](dashboard-file-imports.md).

## Import A File

```bash
uv run issuedeck import-json issues.json \
  --config server.toml \
  --project-key example \
  --kind feature \
  --tag imported
```

Use `--dry-run` first to validate fields, statuses, branches, and counts
without writing to SQLite:

```bash
uv run issuedeck import-json issues.json \
  --config server.toml \
  --project-key example \
  --dry-run
```

## Supported Shapes

Top-level array:

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

Wrapped export:

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

## Fields

Field matching is case-insensitive and treats spaces, dashes, and underscores
as equivalent.

- `title`, `summary`, `name`: item title. This is required.
- `body`, `description`, `notes`, `details`: item body.
- `kind`, `type`, `category`, `issue_type`: row kind. If omitted, `--kind` is
  used.
- `status`, `state`, `workflow`, `workflow_state`: row status. If omitted, the
  first non-terminal project status is used.
- `tags`, `labels`, `keywords`, `label_names`: tags. Arrays of strings and
  objects with `name`, `label`, `value`, `title`, or `key` are supported.
- `applies_to`, `branch`, `branches`, `fix_version`: target branches.
- `external_links`, `links`, `refs`, `references`, `url`, `html_url`: source
  links. GitHub issue, pull request, and commit URLs are normalized.
- `source_id`, `id`, `key`, `identifier`, `issue_key`, `number`: source
  tracker ID copied into the item body.

## Presets And Status Maps

Use presets for common tracker exports:

```bash
uv run issuedeck import-json github-issues.json \
  --config server.toml \
  --project-key example \
  --preset github \
  --status-map open=proposed \
  --status-map closed=done
```

Available presets are `github`, `linear`, `jira`, and `generic`.

Use `--field-alias` for custom JSON keys and `--status-map` for source workflow
states that do not match your project config. Unknown statuses fail the import
before any rows are written.
