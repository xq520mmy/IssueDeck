# Maintainer Workflow

[简体中文](maintainer-workflow.zh-CN.md)

This guide standardizes how IssueDeck maintainers and AI coding windows turn a
request into a reviewed, tested, committed, and pushed change.

## Goals

- Keep every change traceable from requirement to commit.
- Protect private project data and local runtime files.
- Make future coding windows self-sufficient.
- Keep the public repo polished: bilingual docs, passing checks, clean history,
  and no stale UI.

## Requirement Intake

Before implementation, write down or infer the smallest useful requirement:

- Problem: what user pain or product gap is being solved?
- User: who needs it, human dashboard user, CLI user, MCP client, or maintainer?
- Outcome: what must be possible after this change?
- Acceptance criteria: visible behavior, API shape, commands, edge cases, and
  failure messages.
- Non-goals: what should stay out of this change?
- Risk: migrations, secrets, real data, public docs, deployment, or UI impact.

For larger work, create or update a GitHub issue first. The issue should include
context, scope, acceptance criteria, test plan, and any screenshots or examples.

## Planning Standard

Use this short plan before writing code:

1. Locate the affected feature slice and existing patterns.
2. Decide whether tests, docs, i18n, migrations, or CSS generation are needed.
3. Identify a local reproduction or preview path.
4. Define the validation commands that must pass.
5. Keep the change focused enough for a reviewer to understand quickly.

## Implementation Standard

- Follow existing structure: `routes -> service -> repo -> models -> schemas`.
- Prefer existing helpers and domain services over new abstractions.
- Add Alembic migrations for schema changes.
- Keep generated/runtime data out of commits.
- Use fake demo data in docs, fixtures, screenshots, and examples.
- If dashboard copy changes, update both `en` and `zh-CN` in
  `src/issuedeck/features/dashboard/i18n.py`.
- If dashboard templates, helper class maps, or Tailwind config change, run
  `npm run build:css` and commit the generated dashboard CSS.
- If the change affects users, update `CHANGELOG.md`.
- If the change is user-facing, update both English and Chinese docs when
  reasonable.

## UI And I18n Standard

- Read `DESIGN.md` before changing dashboard UI.
- Keep the dashboard dense, structured, code-adjacent, and trustworthy.
- Every visible dashboard string should come from i18n.
- Test or inspect that raw keys such as `nav.import_history`, `nav.import_files`,
  or `bulk.action` never render in HTML.
- Verify important dashboard changes in a local browser or HTTP preview.
- Use `Cache-Control: no-store` for server-rendered dashboard HTML so local
  preview sessions do not show stale translated pages.

## Test Standard

Run focused tests first, then the full suite before commit when behavior changed.

Generic commands:

```bash
uv run ruff check .
uv run pytest
git diff --check
```

Windows workspace commands used by the maintainer machine:

```powershell
C:\Python313\python.exe -m uv run ruff check .
C:\Python313\python.exe -m uv run pytest
git diff --check
```

Dashboard CSS changes:

```bash
npm run build:css
```

Packaging or release checks:

```bash
uv build
```

## Local Preview Standard

Use a fake local token. Never print real secrets.

```powershell
$env:ISSUEDECK_API_TOKEN = "set-via-ISSUEDECK_API_TOKEN-env"
C:\Python313\python.exe -m uv run issuedeck demo --config server.toml --project-key example --host 127.0.0.1 --port 8775
```

If the browser shows stale UI or raw i18n keys:

1. Check ports `8775-8778` for old IssueDeck processes.
2. Stop old preview processes.
3. Start one current server on `8775`.
4. Reopen the affected dashboard URL and verify the HTML no longer contains raw
   translation keys.

## Git Standard

Before committing:

```bash
git status --short
git diff --stat
git diff --check
```

Stage explicit files:

```bash
git add path/to/file path/to/other-file
```

Use Conventional Commits:

- `feat:` user-visible feature.
- `fix:` bug fix.
- `docs:` documentation-only change.
- `test:` tests-only change.
- `refactor:` behavior-preserving code change.
- `chore:` tooling, maintenance, generated metadata, or housekeeping.

Good examples:

```text
feat: add import batch soft delete
fix: prevent stale dashboard translations
docs: add maintainer workflow
```

Push after local checks pass:

```powershell
$env:GIT_CONFIG_GLOBAL = "NUL"
git push origin main
```

## CI Verification

After pushing, confirm the GitHub Actions runs for the pushed SHA. At minimum,
watch:

- `ci`
- `docker`

The final handoff should include:

- Commit SHA and message.
- Local checks run and their result.
- Remote CI/Docker links.
- Preview URL when relevant.
- Any known limitation or follow-up.

## Release Standard

For normal development:

- Add user-facing changes to `CHANGELOG.md` under `[Unreleased]`.
- Do not bump package versions unless preparing an actual release.
- Do not tag a release until tests, Docker, docs, and changelog are ready.

For release work:

1. Review `RELEASE_CHECKLIST.md`.
2. Confirm version numbers in `pyproject.toml` and `package.json`.
3. Confirm `CHANGELOG.md` has the final dated section.
4. Run full tests and build.
5. Push, verify CI, create the tag/release, and verify published artifacts.

## Security And Privacy

- Never commit `.env`, real tokens, private project configs, real tracker data,
  database files, archives, or generated deployment bundles.
- Search for private names before public release changes.
- Prefer fake project names and fake issue data in examples.
- Use environment variables for tokens.
- Redact credentials in logs and final reports.

## Definition Of Done

A change is done when:

- The requirement is satisfied.
- Tests cover the behavior or the risk is explicitly explained.
- Docs, i18n, changelog, CSS, migrations, and examples are updated when needed.
- `ruff`, `pytest`, and `git diff --check` pass.
- UI changes are previewed locally.
- The commit is pushed and remote CI is green when publishing or autonomous
  completion was requested.
