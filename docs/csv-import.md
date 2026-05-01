# CSV Import

[简体中文](csv-import.zh-CN.md)

`issuedeck import-csv` turns tracker exports and spreadsheet rows into
IssueDeck items. It is designed for lightweight migrations from GitHub Issues,
Linear, Jira, Airtable, Notion tables, and hand-maintained CSV files.

The same CSV mapping flow is available in the dashboard through
[Dashboard File Imports](dashboard-file-imports.md).

## Import A File

```bash
uv run issuedeck import-csv issues.csv \
  --config server.toml \
  --project-key example \
  --kind feature \
  --tag imported
```

Use `--dry-run` first to validate columns, statuses, branches, and counts
without writing to SQLite:

```bash
uv run issuedeck import-csv issues.csv \
  --config server.toml \
  --project-key example \
  --dry-run
```

## Columns

Column matching is case-insensitive and treats spaces, dashes, and underscores
as equivalent. For example, `Issue Type`, `issue_type`, and `issue-type` match
the same alias.

Common columns are recognized automatically:

- `title`, `summary`, `name`: item title. This is required.
- `body`, `description`, `notes`, `details`: item body.
- `kind`, `type`, `category`, `issue_type`: row kind. If omitted, `--kind` is
  used.
- `status`, `state`, `workflow`, `workflow_state`: row status. If omitted, the
  first non-terminal project status is used.
- `tags`, `labels`, `keywords`, `label_names`: comma, semicolon, pipe, or
  newline separated tags.
- `applies_to`, `branch`, `branches`, `fix_version`: target branches. If
  omitted, all project branches are used unless `--applies-to` is passed.
- `external_links`, `links`, `refs`, `references`, `url`, `html_url`: source
  links. GitHub issue, pull request, and commit URLs are normalized.
- `source_id`, `id`, `key`, `identifier`, `issue_key`, `number`: source
  tracker ID copied into the item body.

## Presets

Apply common aliases for exported tracker CSVs:

```bash
uv run issuedeck import-csv github-issues.csv \
  --config server.toml \
  --project-key example \
  --preset github \
  --status-map open=proposed \
  --status-map closed=done
```

Available presets:

- `github`
- `linear`
- `jira`
- `generic`

## Custom Aliases

Use `--field-alias` when your CSV headers use different names:

```bash
uv run issuedeck import-csv backlog.csv \
  --config server.toml \
  --project-key example \
  --kind improvement \
  --field-alias title=Issue \
  --field-alias body=Long Description \
  --field-alias status=Workflow
```

Accepted fields are `title`, `body`, `kind`, `status`, `tags`, `applies_to`,
`external_links`, `source_id`, and `source_url`.

## Status Mapping

IssueDeck validates imported statuses against the project config. Common source
states like `open`, `closed`, and `in progress` are mapped automatically when
possible, but explicit mappings are safer for real migrations:

```bash
uv run issuedeck import-csv jira.csv \
  --config server.toml \
  --project-key example \
  --preset jira \
  --status-map "To Do=proposed" \
  --status-map "In Progress=in_progress" \
  --status-map Done=done
```

Unknown statuses fail the import before any rows are written.
