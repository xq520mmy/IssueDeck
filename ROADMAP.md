# Roadmap

IssueDeck is starting small on purpose: a local-first issue deck, a dashboard,
and MCP tools that make coding-agent workflows easier to track.

Current public release: `v0.3.0`.

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
- Delete controls for saved dashboard filters.
- Keyboard-friendly dashboard triage for search, filters, create, navigation,
  and item focus.
- Signed asynchronous lifecycle webhooks for item create, update, ship, delete,
  and restore events.

## Near Term

- PyPI/uvx distribution so new users can try IssueDeck without cloning the repo.
- A tighter first-run onboarding path inside the dashboard after login.
- GitHub import/link helpers that turn issues or PRs into IssueDeck external
  links without requiring a full sync engine.
- More import/export adapters for common Markdown issue formats.
- Webhook receiver examples for common stacks such as FastAPI, Flask, and Node.
- Docker Compose hardening examples for small production deployments.

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
