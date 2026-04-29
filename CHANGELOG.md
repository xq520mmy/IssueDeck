# Changelog

All notable changes to IssueDeck will be documented in this file.

The format loosely follows Keep a Changelog, and this project uses semantic
versioning once public releases begin.

## [Unreleased]

### Added

- One-command local demo flow via `issuedeck demo`.
- MCP client setup guides for Claude Desktop, Claude Code, and Cursor.
- Scoped API tokens for read-only, agent, and admin clients.
- Project-scoped saved dashboard filters stored in the local runtime data directory.
- Markdown frontmatter import schema docs plus field alias mapping for legacy trackers.

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
