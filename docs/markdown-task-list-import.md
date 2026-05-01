# Markdown Task List Import

[简体中文](markdown-task-list-import.zh-CN.md)

`issuedeck import-markdown-list` turns ordinary Markdown task lists into
IssueDeck items. It is meant for lightweight `TODO.md`, GitHub issue
descriptions, release notes, and project planning files that use task list
syntax instead of YAML frontmatter.

The same task-list import flow is available in the dashboard through
[Dashboard File Imports](dashboard-file-imports.md).

## Accepted Syntax

The importer reads Markdown files and recognizes these task forms:

```markdown
- [ ] Add keyboard shortcut hints
- [x] Move old tracker data into IssueDeck
* [ ] Fix dashboard empty state
1. [ ] Review GitHub issue https://github.com/example/repo/issues/42
```

Indented lines below a task are copied into the item body:

```markdown
- [ ] Add export dry-run output
  Keep the wording short and include counts.
```

GitHub issue, pull request, and commit URLs in task text or notes are converted
into normalized external links.

## Import A File

```bash
uv run issuedeck import-markdown-list TODO.md \
  --config server.toml \
  --project-key example \
  --kind feature
```

By default, checked tasks are skipped so completed history does not fill the
active queue. Add `--include-checked` to import checked tasks into the first
terminal status in the project config.

```bash
uv run issuedeck import-markdown-list TODO.md \
  --config server.toml \
  --project-key example \
  --kind feature \
  --include-checked
```

## Import A Directory

Point `source` at a directory to import all non-hidden `*.md` files recursively:

```bash
uv run issuedeck import-markdown-list ./planning \
  --config server.toml \
  --project-key example \
  --kind improvement \
  --tag planning
```

Use `--dry-run` first to print counts without writing to SQLite:

```bash
uv run issuedeck import-markdown-list ./planning \
  --config server.toml \
  --project-key example \
  --dry-run
```

## Options

- `--kind`: IssueDeck kind to create. If omitted, the first project kind is used.
- `--tag`: add a tag to every imported item. Repeat for multiple tags. The
  importer always adds `markdown`.
- `--applies-to`: target a branch. Repeat for multiple branches. If omitted,
  every configured project branch is used.
- `--include-checked`: import checked tasks into the first terminal status.
- `--dry-run`: print the import summary without writing.

For Markdown files that already have YAML frontmatter and explicit IDs, use the
stricter [Markdown Frontmatter Import](markdown-frontmatter-import.md) instead.
