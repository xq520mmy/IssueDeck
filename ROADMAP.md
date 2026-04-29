# Roadmap

IssueDeck is starting small on purpose: a local-first issue deck, a dashboard,
and MCP tools that make coding-agent workflows easier to track.

## Near Term

- PyPI/uvx distribution so new users can try IssueDeck without cloning the repo.
- One-command demo mode that creates config, migrates the database, seeds fake
  data, and opens the dashboard.
- More MCP client examples for common agent environments.
- Dashboard polish for saved filters, keyboard-friendly triage, and denser
  project switching.
- Import/export adapters for common Markdown issue formats.

## Later

- Scoped tokens for read-only, agent, and admin workflows.
- GitHub integration for linking issues, pull requests, commits, and releases.
- Webhooks for item lifecycle events and ship records.
- Optional notification hooks for Slack, Discord, or email.
- A lightweight plugin surface for custom item fields and project templates.

## Contribution Areas

- `good first issue`: small docs, UI, and test improvements.
- `help wanted`: self-contained features with clear behavior.
- `design`: dashboard layout, visual hierarchy, and interaction polish.
- `mcp`: agent-facing tool contracts and workflow ergonomics.
- `deployment`: Docker, offline installs, backup, restore, and operations docs.

The current public release is `v0.1.0`. The project is pre-1.0, so public APIs
may still change while the core workflow settles.

