# Starter Issue Backlog

These are candidate public issues for the first open-source iteration.

## 1. Add a one-command local demo

Labels: `enhancement`, `good first issue`, `area: cli`, `area: docs`

IssueDeck should have a single command or documented script that gets a new
contributor from clone to populated dashboard quickly.

Suggested behavior:

- Copy `server.toml.example` to `server.toml` when missing.
- Apply database migrations.
- Seed fake demo data for the `example` project.
- Print the dashboard URL and demo token instructions.

Acceptance criteria:

- Works on macOS/Linux and Windows PowerShell.
- Does not overwrite an existing non-empty project unless explicitly forced.
- README quickstart can point at the flow.

## 2. Add MCP client setup examples

Labels: `documentation`, `good first issue`, `area: mcp`

The README currently shows one generic MCP config. Add examples for common
agent environments and explain the difference between `ISSUEDECK_TOKEN` and
`ISSUEDECK_API_TOKEN`.

Acceptance criteria:

- Add examples for at least two client environments.
- Keep secrets as placeholders only.
- Mention that the MCP process talks to the REST API and does not touch SQLite.

## 3. Add scoped token support

Labels: `enhancement`, `help wanted`, `area: auth`

IssueDeck currently uses one shared bearer token. Add a path toward multiple
tokens with scopes such as read-only, agent, and admin.

Acceptance criteria:

- Propose a backwards-compatible config format.
- Preserve existing single-token deployments.
- Include tests for allowed and denied requests.

## 4. Add saved dashboard filters

Labels: `enhancement`, `help wanted`, `area: dashboard`

Users should be able to save common dashboard filters such as active bugs,
blocked items, ready-to-ship work, or a tag-specific queue.

Acceptance criteria:

- Saved filters are project-scoped.
- Filters can be selected from the dashboard without manual URL editing.
- The implementation works without external services.

## 5. Improve Markdown import compatibility

Labels: `enhancement`, `help wanted`, `area: migration`

The frontmatter importer expects a specific item shape. Make it easier to
import Markdown issue collections from other tools.

Acceptance criteria:

- Document the currently accepted frontmatter schema.
- Add mapping options for common field aliases such as `type`, `state`, and
  `labels`.
- Add fixtures that cover at least two schema variants.

## 6. Add GitHub link fields for PRs, issues, and commits

Labels: `enhancement`, `help wanted`, `area: integrations`

IssueDeck already tracks ship commits. It should also support optional links
to GitHub issues and pull requests so project state can connect back to code
review.

Acceptance criteria:

- Add a minimal data model for external links.
- Render links in item detail pages.
- Expose links through REST and MCP responses.

## 7. Add backup and restore smoke tests

Labels: `documentation`, `good first issue`, `area: deployment`

The repo includes backup docs and a helper script. Add a smoke-testable restore
path so operators can trust the deployment guide.

Acceptance criteria:

- Document backup and restore with copy-pasteable commands.
- Add a lightweight test or scripted check where practical.
- Keep the flow SQLite-native and Docker-friendly.

## 8. Create a screenshot gallery

Labels: `documentation`, `good first issue`, `area: dashboard`

The README has a demo GIF. Add a small gallery for the main dashboard surfaces:
list, kanban, item detail, search, and project creation.

Acceptance criteria:

- Use fake demo data only.
- Optimize images for repository size.
- Link the gallery from README without overwhelming the top section.
