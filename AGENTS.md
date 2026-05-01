# IssueDeck Agent Workflow

This file is the repo-level operating guide for AI coding windows. It keeps
future sessions aligned on requirements, implementation, validation, git, and
release hygiene. The fuller maintainer workflow lives in
`docs/maintainer-workflow.md` and `docs/maintainer-workflow.zh-CN.md`.

## Product Direction

- Product name: IssueDeck.
- Memory hook: "Lighter than Jira. More stable than Markdown."
- Target users: small teams and AI coding workflows that need a local-first,
  self-hosted tracker.
- Dashboard UI must follow `DESIGN.md`: dense, structured, code-adjacent, and
  trustworthy.

## Start Every Task

1. Run `git status --short`.
2. Read the relevant code and docs before changing files.
3. Protect user work. Never revert changes you did not make unless explicitly
   asked.
4. Keep real/private data out of the repo. Use fake demo data in examples,
   docs, tests, screenshots, and seeded data.
5. For user-facing changes, update tests, docs, i18n, and `CHANGELOG.md` when
   appropriate.

## Requirements Standard

For every feature or non-trivial fix, clarify or infer:

- Problem: what user pain is being solved?
- Scope: what is included and what is explicitly not included?
- Acceptance criteria: what must be true before the work is done?
- Data and privacy impact: does it touch tokens, real project data, imports, or
  exports?
- UX impact: dashboard states, empty states, errors, loading, i18n, and mobile.
- Validation: unit, integration, e2e, local preview, CI, and Docker as needed.

## Implementation Rules

- Prefer existing feature slices and patterns:
  `routes -> service -> repo -> models -> schemas`.
- Use Alembic migrations for schema changes.
- Keep edits focused. Avoid unrelated refactors.
- Dashboard template or class changes require `npm run build:css` and committing
  `src/issuedeck/features/dashboard/static/css/dashboard.css` if it changes.
- Dashboard strings must go through `src/issuedeck/features/dashboard/i18n.py`
  for both `en` and `zh-CN`. Do not let raw keys such as `nav.*` or `bulk.*`
  render in HTML.
- Public docs should be bilingual when the feature is user-facing.

## Required Checks

Use the generic commands below. In this Windows workspace, `uv` may need to be
called through `C:\Python313\python.exe -m uv`.

```powershell
C:\Python313\python.exe -m uv run ruff check .
C:\Python313\python.exe -m uv run pytest
git diff --check
```

When dashboard CSS may change:

```powershell
npm run build:css
```

Before packaging or release:

```powershell
C:\Python313\python.exe -m uv build
```

## Local Preview

Use a fake token for local preview and never print real secrets.

```powershell
$env:ISSUEDECK_API_TOKEN = "set-via-ISSUEDECK_API_TOKEN-env"
C:\Python313\python.exe -m uv run issuedeck demo --config server.toml --project-key example --host 127.0.0.1 --port 8775
```

If UI looks stale, check for old preview servers on ports `8775-8778`, stop the
old processes, and restart one current server.

## Git Standard

- Review `git diff --stat` and the important diff before committing.
- Stage explicit files, not broad generated or runtime directories.
- Use Conventional Commits:
  - `feat:` user-visible feature
  - `fix:` bug fix
  - `docs:` documentation only
  - `test:` tests only
  - `refactor:` behavior-preserving code change
  - `chore:` tooling or maintenance
- Push only after local checks pass.

Preferred push command in this workspace:

```powershell
$env:GIT_CONFIG_GLOBAL = "NUL"
git push origin main
```

After pushing, verify GitHub Actions for the pushed SHA. Final reports should
include the commit SHA, checks run, CI/Docker links, and any residual risk.

## Done Means Done

A task is complete only when:

- The requested behavior is implemented.
- Regression coverage exists for behavior changes.
- Relevant docs, i18n, generated CSS, and changelog entries are updated.
- Local checks pass.
- Local preview is verified for UI changes.
- Changes are committed, pushed, and remote CI is green when the user asked for
  autonomous completion or publishing.
