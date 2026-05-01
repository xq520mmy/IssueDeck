# Contributing to IssueDeck

Thanks for helping make IssueDeck better.

IssueDeck is a lightweight, self-hosted development tracker for small teams and
AI coding workflows. The product memory hook is:

> Lighter than Jira. More stable than Markdown.

## Development Setup

```bash
uv sync
uv run alembic upgrade head
uv run pytest
uv run ruff check .
```

If `uv` is not installed, see the official uv installation guide.
Node.js is only required when you change dashboard styles.

## Local Configuration

Copy the examples before running the server:

```bash
cp server.toml.example server.toml
cp projects/example.toml projects/myproject.toml
```

Set a local token through the environment:

```bash
export ISSUEDECK_API_TOKEN="issuedeck-local-token"
```

On Windows PowerShell:

```powershell
$env:ISSUEDECK_API_TOKEN = "issuedeck-local-token"
```

## Quality Gates

Before opening a pull request, run:

```bash
uv run ruff check .
uv run pytest
uv build
```

All should pass. CI also verifies the generated dashboard CSS is committed and
builds the Docker image to catch packaging and deployment regressions.

For maintainer-side requirement intake, AI coding-window handoffs, git commits,
pushes, CI verification, and release hygiene, follow
[Maintainer Workflow](docs/maintainer-workflow.md).

## Design Work

Read `DESIGN.md` before changing dashboard UI, templates, colors, spacing, or
motion. UI changes should reinforce the Industrial Developer Ledger direction:
dense, structured, code-adjacent, and trustworthy.

Dashboard styles are compiled with Tailwind. After changing dashboard
templates, helper class maps, or `tailwind.config.cjs`, run:

```bash
npm ci
npm run build:css
```

Then include `src/issuedeck/features/dashboard/static/css/dashboard.css` in the
same change.

Before submitting dashboard UI changes, run the lightweight
[Dashboard Accessibility Smoke Checklist](docs/accessibility-checklist.md).

## Pull Request Guidelines

- Keep changes focused and easy to review.
- Add or update tests when behavior changes.
- Do not commit local runtime data, private project configs, `.env` files, or
  generated deployment archives.
- Prefer existing feature-sliced structure: `routes -> service -> repo -> models`.
- Document user-facing changes in `CHANGELOG.md`.

## Reporting Bugs

Include:

- IssueDeck version or commit SHA.
- Python version and operating system.
- Deployment mode: local, Docker, or offline Docker.
- Steps to reproduce.
- Expected and actual behavior.
