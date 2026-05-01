# GitHub Issues Import

[简体中文](github-issues-import.zh-CN.md)

`issuedeck import-github-issues` imports issues from a GitHub repository through
the GitHub REST API. It is intentionally lightweight: it creates local
IssueDeck items with normalized GitHub external links, skips items that were
already imported, and does not mirror comments or maintain a two-way sync loop.

## Dashboard Import

Open a project in the dashboard, then choose **Import GitHub** from the sidebar.
The form supports `owner/repo` or a GitHub repository URL, state and label
filters, status mapping, branch targets, optional tags, and an optional token.

Use **Preview import** first to see fetched, skipped, planned, and duplicate
counts without writing anything. Use **Import issues** to create the new
IssueDeck items.

Successful dashboard imports add a unique `github-import-YYYYMMDD-HHMMSS-xxxx`
batch tag to the items written by that run. The result panel links directly to
the list filtered by that tag, so you can bulk-triage only the new items.

After importing a large backlog, use [Dashboard Bulk Triage](dashboard-bulk-triage.md)
to select multiple items and assign status, tags, kinds, or branches in one pass.

## Import Open Issues

```bash
uv run issuedeck import-github-issues example/repo \
  --config server.toml \
  --project-key example \
  --kind feature
```

The repo can be `owner/repo` or a full repository URL such as
`https://github.com/example/repo`.

## Authentication

Public repositories can be imported without a token, but authenticated requests
have higher rate limits and can access private repositories.

```bash
export GITHUB_TOKEN="ghp_..."
uv run issuedeck import-github-issues example/private-repo \
  --config server.toml \
  --project-key example
```

PowerShell:

```powershell
$env:GITHUB_TOKEN = "ghp_..."
uv run issuedeck import-github-issues example/private-repo `
  --config server.toml `
  --project-key example
```

You can also pass `--github-token` for one command.

## Repeatable Imports

The importer checks existing IssueDeck external links for the same project and
skips GitHub issue URLs that are already present. This makes it safe to run the
same import again after more GitHub issues are created.

```bash
uv run issuedeck import-github-issues example/repo \
  --config server.toml \
  --project-key example \
  --state all \
  --status-map open=proposed \
  --status-map closed=done \
  --limit 100
```

## Filters

- `--state open|closed|all`: GitHub issue state to fetch. Default: `open`.
- `--label bug`: only fetch issues with a label. Repeat for multiple labels.
- `--since 2026-01-01T00:00:00Z`: only fetch issues updated after a timestamp.
- `--limit 50`: maximum imported issues. Default: `50`.
- `--include-pulls`: include pull requests returned by GitHub's issues endpoint.

By default, pull requests are skipped because GitHub returns PRs from the
issues endpoint with a `pull_request` marker.

## Mapping

- GitHub issue title becomes the IssueDeck title.
- GitHub issue body is copied into the IssueDeck body, followed by source
  metadata.
- GitHub labels become IssueDeck tags, plus the default `github` tag.
- GitHub state is mapped to project status. `open` maps to the first
  non-terminal status by default, and `closed` maps to the first terminal status
  unless overridden with `--status-map`.

Preview without writing:

```bash
uv run issuedeck import-github-issues example/repo \
  --config server.toml \
  --project-key example \
  --dry-run
```
