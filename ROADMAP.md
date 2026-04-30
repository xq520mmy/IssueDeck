# Roadmap

IssueDeck is starting small on purpose: a local-first issue deck, a dashboard,
and MCP tools that make coding-agent workflows easier to track.

Current public release: `v0.3.2`.

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
- Webhook receiver examples for FastAPI, Flask, and Node/Express.
- Docker Compose hardening examples for small production deployments.
- Dashboard accessibility smoke checklist for UI contributors.

## Near Term

- More import/export adapters for JSON and hosted tracker exports.
- Release-announcement polish for project pages, screenshots, and examples.

## Later

- Optional notification hooks for Slack, Discord, or email.
- A lightweight plugin surface for custom item fields and project templates.
- Project-level audit/export bundles for teams that need periodic snapshots.

## Contribution Areas

- `good first issue`: small docs, UI, and test improvements.
- `help wanted`: self-contained features with clear behavior.
- `design`: dashboard layout, visual hierarchy, and interaction polish.
- `mcp`: agent-facing tool contracts and workflow ergonomics.
- `deployment`: Docker, offline installs, backup, restore, and operations docs.

IssueDeck is pre-1.0, so public APIs may still change while the core workflow
settles.
