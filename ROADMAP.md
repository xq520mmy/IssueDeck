# Roadmap

IssueDeck is starting small on purpose: a local-first issue deck, a dashboard,
and MCP tools that make coding-agent workflows easier to track.

Current public release: `v0.5.0`.

The `main` branch may include unreleased contributor-experience improvements
listed in `CHANGELOG.md`.

## Shipped in v0.3

- One-command local demo mode with fake project data.
- MCP client setup guides for Claude Desktop, Claude Code, and Cursor.
- Scoped API tokens for read-only, agent, and admin workflows.
- Dashboard project creation, saved filters, language switching, and screenshot
  gallery.
- Markdown frontmatter import, export, and backup restore smoke checks.
- External links for GitHub issues, pull requests, commits, and other review
  context.
- Docker Compose deployment, GHCR images, release assets, and SHA256 checksums.
- GitHub issue forms, PR template, and security policy.
- Dashboard onboarding empty states for fresh installs and empty projects.
- Dashboard first-run setup checklist after login for new or demo projects.
- Delete controls for saved dashboard filters.
- Keyboard-friendly dashboard triage for search, filters, create, navigation,
  and item focus.
- Signed asynchronous lifecycle webhooks for item create, update, ship, delete,
  and restore events.
- PyPI/uvx distribution so new users can try IssueDeck without cloning the repo.
- GitHub URL helper that creates linked IssueDeck items from issue, pull
  request, and commit URLs without a full sync engine.
- Markdown task-list importer for `TODO.md`, planning files, and GitHub
  checklist-style issue descriptions.
- CSV importer for tracker exports and spreadsheet rows, with presets, column
  aliases, status mapping, and dry-run validation.
- JSON importer for arrays, single objects, and wrapped tracker exports.
- Webhook receiver examples for FastAPI, Flask, and Node/Express.
- Docker Compose hardening examples for small production deployments.
- Dashboard accessibility smoke checklist for UI contributors.
- Maintainer launch kit with project-page copy, topics, demo script, and
  public sharing snippets.
- Hosted tracker export helper docs for GitHub Issues, Linear, Jira, and
  generic tables.
- Built-in project templates for first-run dashboard project creation.
- Project-level audit/export ZIP bundles for periodic snapshots.
- Dashboard download controls for project-level audit/export bundles.
- Slack and Discord lifecycle notifications for team-visible item updates.
- Local project-template packs for custom starter workflows without source
  changes.

## Near Term

- Add optional email notifications for teams that prefer inbox workflows.
- Explore a lightweight plugin surface for custom item fields and richer
  third-party extensions.

## Later

- Project template marketplace docs once third-party templates exist.

## Contribution Areas

- `good first issue`: small docs, UI, and test improvements.
- `help wanted`: self-contained features with clear behavior.
- `design`: dashboard layout, visual hierarchy, and interaction polish.
- `mcp`: agent-facing tool contracts and workflow ergonomics.
- `deployment`: Docker, offline installs, backup, restore, and operations docs.

IssueDeck is pre-1.0, so public APIs may still change while the core workflow
settles.
