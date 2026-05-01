# Dashboard File Imports

[简体中文](dashboard-file-imports.zh-CN.md)

The dashboard can import CSV, JSON, and Markdown task-list files without using
the CLI.

Open a project, choose **Import Files** from the sidebar, upload a file, and run
**Preview import** first. Preview parses the file, applies field aliases, status
maps, presets, tags, and branch targets, but does not write items.

Use **Import items** after the preview looks right. Successful imports add a
unique `csv-import-*`, `json-import-*`, or `markdown-import-*` batch tag to the
items written by that run. The result panel links directly to the filtered list,
so the new items can be bulk-triaged immediately.

## Supported Formats

- CSV tracker exports and spreadsheets, using the same mapping rules as
  [`import-csv`](csv-import.md).
- JSON arrays or wrapped exports such as `{ "issues": [...] }`, using the same
  mapping rules as [`import-json`](json-import.md).
- GitHub-style Markdown task lists, using the same parsing rules as
  [`import-markdown-list`](markdown-task-list-import.md).

## CSV and JSON Options

- `Presets`: optional aliases for common export formats. Supported values:
  `github`, `jira`, `linear`, and `generic`.
- `Field aliases`: one `FIELD=alias[,alias...]` mapping per line. Supported
  fields are `title`, `body`, `kind`, `status`, `tags`, `applies_to`,
  `external_links`, `source_id`, and `source_url`.
- `Status map`: one `SOURCE=TARGET` mapping per line, such as `closed=done`.

## Markdown Options

Markdown imports skip checked tasks by default. Enable **Include checked
Markdown tasks** to import them into the first terminal project status.
