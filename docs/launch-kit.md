# IssueDeck Launch Kit

Use this when sharing the first public release of IssueDeck.

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

## Social Post

I just released IssueDeck v0.3.0.

It is a local-first issue deck for small teams and AI coding workflows:

- Web dashboard for humans
- MCP tools for coding agents
- SQLite storage
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
Markdown import/export, scoped tokens, Docker deployment, and signed lifecycle
webhooks.

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
- Roadmap: https://github.com/xq520mmy/IssueDeck/blob/main/ROADMAP.md
- Starter issues: https://github.com/xq520mmy/IssueDeck/blob/main/docs/launch-issues.md
