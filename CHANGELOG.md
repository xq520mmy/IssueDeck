# Changelog

All notable changes to IssueDeck will be documented in this file.

The format loosely follows Keep a Changelog, and this project uses semantic
versioning once public releases begin.

## [Unreleased]

### Added

- Added launch-kit docs with reusable public release copy and links for first
  open-source sharing.
- Expanded the starter issue backlog for contributor-friendly docs and
  deployment follow-ups.

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
