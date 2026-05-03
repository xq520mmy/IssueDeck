# IssueDeck Launch Kit

Use this when sharing IssueDeck publicly on GitHub, X/Twitter, Hacker News,
Reddit, Discord, or a developer community.

## GitHub Project Page

Suggested repository description:

> Local-first issue deck for humans and AI coding agents: dashboard, MCP tools,
> SQLite, and CSV/JSON/Markdown imports.

Suggested topics:

```text
issue-tracker, mcp, ai-agents, coding-agents, fastapi, sqlite, self-hosted,
local-first, developer-tools, project-management
```

Suggested social preview:

```text
docs/assets/issuedeck-social-preview.png
```

Primary demo asset:

```text
docs/assets/issuedeck-v0.8-demo.gif
```

## Short Pitch

IssueDeck is a local-first, self-hosted issue deck for small teams and AI
coding agents. It gives humans a dashboard, gives agents MCP tools, and keeps
work items in one FastAPI + SQLite service instead of scattered Markdown files.

Tagline:

> Lighter than Jira. More stable than Markdown.

Try it:

```bash
uvx issuedeck demo --open
```

## Feature Bullets

- Web dashboard for humans.
- MCP tools for coding agents.
- SQLite local storage with multi-project configs.
- CSV, JSON, Markdown task-list, and Markdown frontmatter imports.
- GitHub issue, pull request, and commit external links.
- Signed lifecycle webhooks for downstream automation.
- Docker/GHCR images and PyPI/uvx install path.
- Fake demo data for safe public screenshots.

## 30-Second Demo Script

1. Run `uvx issuedeck demo --open`.
2. Sign in with `issuedeck-local-token`.
3. Open the list and kanban views.
4. Create one fake item and attach a GitHub URL.
5. Show search, item detail, and the activity timeline.

To test unreleased `main` instead of the latest PyPI release:

```bash
uvx --from git+https://github.com/xq520mmy/IssueDeck issuedeck demo --open
```

## Social Post

I just released IssueDeck.

It is a local-first issue deck for small teams and AI coding workflows:

- Web dashboard for humans
- MCP tools for coding agents
- SQLite storage
- CSV/JSON/Markdown imports
- Fake demo data for safe screenshots
- Docker/GHCR release images
- Signed lifecycle webhooks

Try it:

```bash
uvx issuedeck demo --open
```

Repo: https://github.com/xq520mmy/IssueDeck

## Hacker News / Forum Draft

Show HN: IssueDeck - a local-first issue tracker for humans and AI coding agents

I built IssueDeck because Markdown issue trackers are convenient until multiple
projects, agents, releases, links, and search all need to agree on one source
of truth.

IssueDeck runs as a small FastAPI + SQLite service. Humans use the dashboard;
coding agents use MCP tools over the REST API. It supports multi-project
configs, full-text search, relationships, activity timelines, ship records,
CSV/JSON/Markdown imports, Markdown export, scoped tokens, Docker deployment,
and signed lifecycle webhooks.

The demo path uses fake data by default:

```bash
uvx issuedeck demo --open
```

To test unreleased changes from `main`, use `uvx --from git+...`.

## Useful Links

- Repository: https://github.com/xq520mmy/IssueDeck
- PyPI: https://pypi.org/project/issuedeck/
- Latest release: https://github.com/xq520mmy/IssueDeck/releases/latest
- Screenshot gallery: https://github.com/xq520mmy/IssueDeck/blob/main/docs/gallery.md
- Demo GIF: https://github.com/xq520mmy/IssueDeck/blob/main/docs/assets/issuedeck-v0.8-demo.gif
- Roadmap: https://github.com/xq520mmy/IssueDeck/blob/main/ROADMAP.md
- Starter issues: https://github.com/xq520mmy/IssueDeck/blob/main/docs/launch-issues.md
- CSV import: https://github.com/xq520mmy/IssueDeck/blob/main/docs/csv-import.md
- JSON import: https://github.com/xq520mmy/IssueDeck/blob/main/docs/json-import.md
- Hosted tracker exports: https://github.com/xq520mmy/IssueDeck/blob/main/docs/hosted-tracker-exports.md
