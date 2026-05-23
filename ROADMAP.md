# Roadmap

IssueDeck is starting small on purpose: a local-first issue deck, a dashboard,
and MCP tools that make coding-agent workflows easier to track.

Current public release: `v0.8.0`.

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
- Slack, Discord, and email lifecycle notifications for team-visible item updates.
- Local project-template packs for custom starter workflows without source
  changes.
- Local CLI project template listing and project config creation.
- Project-defined custom fields for item metadata, dashboard forms, exports,
  and API payloads.
- Custom-field list filters and CSV/JSON import mappings.
- Custom-field bulk updates for post-import triage.
- Custom-field chips in list, mobile, and kanban item summaries.
- Custom-field range and presence filters for REST, dashboard, saved filters,
  and pagination.
- Built-in project templates with custom-field presets for lightweight,
  agent-assisted, and software-team workflows.
- MCP tools can create, update, and filter items with custom fields.
- MCP bulk update support for agent-driven post-import triage.
- Local CLI item creation with tags, branches, custom fields, external links,
  body files, JSON output, and dry-run previews.
- Local CLI item updates with status, tags, branches, custom fields, external
  link replacement, body files, append-body support, JSON output, and dry-runs.
- Local CLI bulk updates for status, tags, branches, custom fields, deletion,
  and restore.
- Local CLI shipping with branch, version, commit records, JSON output, and
  dry-run previews.
- Local CLI timeline events for comments, verification notes, handoffs,
  metadata, JSON output, and dry-run previews.
- Local CLI item listing with REST-aligned filters and JSON output.
- Local CLI item detail output for terminal-first triage.
- Installable local template-pack examples for support queues, content
  calendars, and research workflows.
- Local CLI export from existing project configs into reusable template packs.

## Near Term

- Explore richer third-party extension points beyond project templates.
- Collect community template-pack patterns for future marketplace-style docs.

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
