# Roadmap

IssueDeck is starting small on purpose: a local-first issue deck, a dashboard,
and MCP tools that make coding-agent workflows easier to track.

Current public release: `v0.2.1`.

The `main` branch may include unreleased contributor-experience improvements
listed in `CHANGELOG.md`.

## Shipped in v0.2

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

## Near Term

- PyPI/uvx distribution so new users can try IssueDeck without cloning the repo.
- A tighter first-run onboarding path inside the dashboard after login.
- GitHub import/link helpers that turn issues or PRs into IssueDeck external
  links without requiring a full sync engine.
- Keyboard-friendly dashboard triage for list and kanban views.
- More import/export adapters for common Markdown issue formats.

## Later

- Webhooks for item lifecycle events and ship records.
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
