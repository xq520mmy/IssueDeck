# Support

IssueDeck is a small open-source project. The fastest way to get help is to
choose the narrowest public channel that matches the question.

## Where to Ask

- Bug reports: open a GitHub issue with the bug template.
- Feature ideas: open a GitHub issue with the feature request template.
- Documentation gaps: open a GitHub issue with the docs template.
- Security issues: follow `SECURITY.md` and do not open a public issue.

## Before Opening an Issue

Please include:

- IssueDeck version or commit SHA.
- Deployment mode: local `uv`, Docker Compose, or offline Docker.
- Python version and operating system.
- Browser name/version for dashboard issues.
- The smallest reproduction steps you can write.

Do not paste real tokens, private project names, production tracker data, or
private database dumps. Use fake project/item data when sharing examples.

For common first-run problems, start with
[First-run Troubleshooting](docs/troubleshooting.md).

## Self-checks

For local development:

```bash
uv sync
uv run pytest
uv run ruff check .
```

For Docker deployment:

```bash
docker compose pull
docker compose up -d
curl -fsS http://127.0.0.1:8765/readyz
```

For restore checks:

```bash
python scripts/restore_smoke.py backups/tracker-YYYYMMDD-HHMMSS.db.gz \
  --out /tmp/issuedeck-restore-smoke.db
```
