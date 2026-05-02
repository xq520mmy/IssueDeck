# Audit Bundles

Audit bundles are ZIP snapshots for teams that need periodic project archives,
handoffs, or lightweight migration checkpoints.

From the dashboard, open a project overview and use **Export snapshot**.

```bash
uv run issuedeck export-audit-bundle \
  --project-key example \
  --out snapshots/
```

If `--out` is a directory, IssueDeck writes
`snapshots/example-audit-bundle.zip`. If it ends in `.zip`, IssueDeck writes that
exact file.

## Bundle Contents

- `manifest.json`: bundle format, project key, generated timestamp, counts, and
  file list.
- `project.json`: parsed project configuration.
- `project.toml`: original project config, when the TOML exists on disk.
- `items.json`: active and deleted items with tags, branch targets, external
  links, ship records, and lifecycle events.
- `relationships.json`: all relationship rows in the project, including
  bidirectional inverse rows.
- `work_sessions.json`: agent work sessions and progress updates.
- `import_batches.json`: dashboard and CLI import history metadata.

The bundle is read-only and does not mutate project data.
