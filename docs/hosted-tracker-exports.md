# Hosted Tracker Export Helpers

[简体中文](hosted-tracker-exports.zh-CN.md)

IssueDeck does not need a full hosted-tracker sync engine for small migrations.
Export a file from the source tool, dry-run the import, then write the rows into
your local IssueDeck project.

## GitHub Issues

With the GitHub CLI:

```bash
gh issue list \
  --repo OWNER/REPO \
  --state all \
  --limit 1000 \
  --json number,title,state,labels,url,body \
  > github-issues.json
```

Import into IssueDeck:

```bash
uv run issuedeck import-json github-issues.json \
  --config server.toml \
  --project-key example \
  --preset github \
  --status-map OPEN=proposed \
  --status-map CLOSED=done \
  --dry-run
```

Remove `--dry-run` once the counts and status mappings look right.

## Linear

In Linear, export issues to CSV from workspace settings or the relevant team
view. Then import the CSV:

```bash
uv run issuedeck import-csv linear-issues.csv \
  --config server.toml \
  --project-key example \
  --preset linear \
  --status-map Backlog=proposed \
  --status-map Todo=proposed \
  --status-map "In Progress=in_progress" \
  --status-map Done=done \
  --dry-run
```

If your Linear export uses custom workflow names, map them explicitly with
additional `--status-map SOURCE=TARGET` options.

## Jira

In Jira, filter the issues you want, then use **Export CSV**. The preset covers
common fields such as `Summary`, `Description`, `Issue Type`, `Status`,
`Labels`, `Fix Version/s`, `Key`, and URL-like fields.

```bash
uv run issuedeck import-csv jira-issues.csv \
  --config server.toml \
  --project-key example \
  --preset jira \
  --status-map "To Do=proposed" \
  --status-map "In Progress=in_progress" \
  --status-map Done=done \
  --dry-run
```

## Generic Tables

For Airtable, Notion, Google Sheets, or hand-maintained tables, export CSV and
map your custom headers:

```bash
uv run issuedeck import-csv backlog.csv \
  --config server.toml \
  --project-key example \
  --preset generic \
  --field-alias title=Issue \
  --field-alias body=Notes \
  --field-alias status=Stage \
  --field-alias tags=Tags \
  --dry-run
```

## Before You Write

- Run with `--dry-run` first.
- Confirm source statuses map to real IssueDeck statuses.
- Confirm branch names match the project config, or omit branch columns to use
  all configured branches.
- Keep the original export file until you have reviewed the imported items.
