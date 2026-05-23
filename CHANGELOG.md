# Changelog

All notable changes to IssueDeck will be documented in this file.

The format loosely follows Keep a Changelog, and this project uses semantic
versioning once public releases begin.

## [Unreleased]

### Added

- Added `issuedeck validate-project-templates` for local template-pack TOML
  validation with table and JSON output.
- Added `issuedeck list-project-template-examples` and
  `issuedeck install-project-template-example` with support, content, and
  research template-pack examples.

## [0.8.0] - 2026-05-02

### Added

- Added `issuedeck list-project-templates` and `issuedeck create-project` for
  template-based project config creation from the local CLI.
- Added `issuedeck create-item` for local CLI item creation with tags,
  branches, custom fields, external links, body files, JSON output, and dry-run
  previews.
- Added `issuedeck update-item` for local CLI item updates with status, tags,
  branches, custom fields, external link replacement, body files, append-body
  support, JSON output, and dry-run previews.
- Added `issuedeck bulk-update-items` for local CLI bulk status, tag, branch,
  custom-field, delete, and restore workflows.
- Added `issuedeck ship-item` for local CLI ship records with branch, version,
  commits, JSON output, and dry-run previews.
- Added `issuedeck append-item-event` for local CLI comments, verification
  notes, handoff events, metadata, JSON output, and dry-run previews.
- Added `issuedeck list-items` for local CLI item listing with the same kind,
  status, tag, branch, relationship, custom-field, and deletion filters as the
  REST list API.
- Added `issuedeck get-item` for local CLI item detail output in text or JSON.

## [0.7.0] - 2026-05-02

### Added

- Added range and presence filters for project custom fields in REST list
  queries, dashboard filters, saved filters, and pagination links.
- Added built-in custom-field presets to project templates.
- Added MCP create/update/list support for item custom fields.
- Added an MCP bulk-update tool for agent-driven triage across many items.

## [0.6.0] - 2026-05-02

### Added

- Added optional Slack, Discord, and email lifecycle notifications.
- Added local project-template packs through `project_templates_dir` so new
  dashboard projects can start from custom TOML templates without code changes.
- Added project-defined custom fields with REST, dashboard, Markdown export,
  and audit-bundle support.
- Added custom-field support to local project-template packs.
- Added dashboard/API custom-field list filters and CSV/JSON import mappings.
- Added custom-field support to REST and dashboard bulk updates.
- Added custom-field chips to dashboard list, mobile, and kanban item summaries.

## [0.5.0] - 2026-05-02

### Added

- Added Agent Work Sessions for tracking active, paused, completed, and
  canceled coding-agent work across REST, MCP tools, the dashboard, and demo data.
- Added `issuedeck import-github-issues` for repeatable, lightweight GitHub
  repository issue imports with label/state filters and duplicate skipping.
- Added a dashboard GitHub Issues import page with preview, status mapping,
  branch targets, optional tokens, and duplicate-skipping summaries.
- Added dashboard and REST bulk triage for selected items, including status,
  kind, tag, branch, delete, and restore operations.
- Linked dashboard GitHub imports to bulk triage with per-import batch tags and
  filtered result links.
- Added dashboard file imports for CSV, JSON, and Markdown task lists with
  preview, field aliases, status maps, batch tags, and bulk-triage links.
- Added dashboard import history for reopening successful GitHub, CSV, JSON,
  and Markdown import batches.
- Added a dashboard import-history action for soft-deleting all active items
  from a recorded import batch.
- Added a dashboard import-history restore action for recovering soft-deleted
  items from an import batch.
- Added active/deleted item counts to dashboard import history and disabled
  empty batch delete or restore actions.
- Added source and item-state filters to dashboard import history.
- Added pagination to dashboard import history while preserving selected filters.
- Added built-in starter templates to dashboard project creation.
- Added `issuedeck export-audit-bundle` for project-level ZIP snapshots.
- Added dashboard audit-bundle downloads from the project overview.
- Added maintainer workflow docs for requirements, validation, git commits,
  pushes, and CI checks.
- Documented local browser recovery steps and disabled caching for root
  dashboard redirects to reduce stale preview pages.

## [0.4.0] - 2026-05-01

### Added

- Added `issuedeck import-github-url` for creating IssueDeck items linked to
  GitHub issue, pull request, and commit URLs.
- Added `issuedeck import-markdown-list` for turning plain Markdown task lists
  into IssueDeck items.
- Added `issuedeck import-csv` with common tracker presets, custom column
  aliases, status mapping, and dry-run validation.
- Added `issuedeck import-json` for top-level arrays, single objects, and
  wrapped tracker exports such as `items`, `issues`, `data`, `records`, or
  `tasks`.
- Added a compact dashboard setup checklist for first-run projects after login.
- Added hosted tracker export helper docs for GitHub Issues, Linear, Jira, and
  generic table sources.

### Changed

- Expanded the launch kit with GitHub project-page copy, suggested topics,
  demo assets, feature bullets, and 30-second demo scripts in English and
  Chinese.

### Fixed

- `issuedeck serve` and `issuedeck seed-demo` now apply database migrations
  before touching SQLite, preventing stale local databases from returning
  dashboard 500 errors after upgrades.

## [0.3.2] - 2026-04-30

### Fixed

- Aligned the runtime `issuedeck.__version__` value with the published package
  version so health checks report the current release.

## [0.3.1] - 2026-04-30

### Added

- Added launch-kit docs with reusable public release copy and links for first
  open-source sharing.
- Expanded the starter issue backlog for contributor-friendly docs and
  deployment follow-ups.
- Added webhook receiver examples for FastAPI, Flask, and Node/Express.
- Added Docker Compose hardening notes for small self-hosted deployments.
- Added a dashboard accessibility smoke checklist for UI contributions.
- Added PyPI Trusted Publishing troubleshooting notes for `invalid-publisher`
  failures.
- Updated public install docs now that `issuedeck` is published on PyPI.

### Changed

- Refreshed README, roadmap, and security policy copy for the `v0.3.0` public
  release.

## [0.3.0] - 2026-04-30

### Added

- Added dashboard onboarding empty states for fresh installs and empty projects.
- Added delete controls for project-scoped saved dashboard filters.
- Added first-run troubleshooting docs for setup, token, SQLite, and Docker issues.
- Added GitHub URL inference for item external links in API/MCP payloads and dashboard forms.
- Added keyboard-friendly dashboard shortcuts for search, create, filters, navigation, and item focus.
- Added Markdown import adapter presets for GitHub, Linear, and generic tracker exports.
- Added signed asynchronous lifecycle webhooks for item create, update, ship, delete, and restore events.
- Added a gated PyPI Trusted Publishing workflow and PyPI setup guide for future `uvx issuedeck` installs.
- Added PyPI project URLs and license-file metadata to the Python package.
- Added Dependabot version updates for Python/uv, npm, and GitHub Actions.
- Added `SUPPORT.md` plus refreshed issue, pull request, security, and roadmap guidance for contributors.

### Fixed

- Fixed fresh dashboard installs rendering broken project links when no projects exist yet.
- Fixed generated Tailwind CSS drift between Windows and Linux builds.

### Changed

- Raised Python dependency floors for FastAPI, Uvicorn, SQLAlchemy, Pydantic, and Pydantic Settings.
- Upgraded dashboard CSS builds to Tailwind CSS v4.

## [0.2.1] - 2026-04-29

### Added

- Published Docker images to GitHub Container Registry for stable releases and `edge`.
- Automated release artifacts with Python distributions and `SHA256SUMS.txt`.
- Docker Compose now starts from the published GHCR image by default, with a local-image override for source builds.
- Docker containers now run `uv` with `--no-dev` so production startup does not install development tools.
- Docker build contexts now exclude private project configs, SQLite databases, backups, and temporary files.
- Refreshed English and Chinese deployment docs for one-command Docker startup, pinned versions, offline transfer, and release checksums.

## [0.2.0] - 2026-04-29

### Added

- One-command local demo flow via `issuedeck demo`.
- MCP client setup guides for Claude Desktop, Claude Code, and Cursor.
- Scoped API tokens for read-only, agent, and admin clients.
- Project-scoped saved dashboard filters stored in the local runtime data directory.
- Markdown frontmatter import schema docs plus field alias mapping for legacy trackers.
- Item external links for GitHub issues, pull requests, and commits in REST, MCP, and dashboard detail views.
- SQLite backup restore smoke script with copy-pasteable Docker restore docs.
- Screenshot gallery for list, kanban, item detail, search, and project creation surfaces.

## [0.1.0] - 2026-04-29

### Added

- FastAPI REST server for multi-project item tracking.
- MCP stdio client with tools for projects, items, shipping, search, and relationships.
- SQLite storage with Alembic migrations and FTS5 search.
- Item activity timeline with automatic lifecycle events and manual comments.
- Built-in dashboard work queues for backlog, active, blocked, ready-to-ship,
  done, deleted, and recently touched items.
- Fake demo data seeding for public screenshots and README demos.
- Dashboard project creation and language switch foundation.
- Simplified Chinese README.
- Markdown bundle export and generic frontmatter migration command.
- Server-rendered dashboard foundation.
- Token-backed dashboard login with an HTTP-only signed session cookie.
- `/readyz` endpoint for unauthenticated deployment readiness checks.
- Third-party notices for vendored dashboard browser assets.
- Industrial Developer Ledger design system in `DESIGN.md`.
- Docker and offline deployment assets.
- Compiled dashboard CSS build pipeline for production-safe, CDN-free styling.
- Release checklist for pre-tag validation.

### Fixed

- Aligned MCP tool payloads and routes with REST API names for `applies_to`, `after`, and item-scoped relationships.
- Improved mobile dashboard list layout with compact item cards instead of a clipped table.
- Made dashboard sidebar open/closed state independent of runtime Tailwind class generation.
- Accepted UTF-8 BOM in TOML config files, which helps Windows-edited configs load reliably.

### Changed

- Refined dashboard visual direction around the "Lighter than Jira. More stable than Markdown." positioning.
- CI now verifies lint, tests, Python package builds, and Docker image builds.
- Dashboard now ships prebuilt CSS instead of using Tailwind's browser build at runtime.
