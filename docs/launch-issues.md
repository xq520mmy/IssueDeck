# Starter Issue Backlog

These track public issues for the next open-source iterations. Completed items
remain here as examples of contributor-sized work with clear acceptance
criteria. The original launch backlog has mostly shipped: one-command demo
mode, MCP client examples, scoped tokens, saved dashboard filters, Markdown
frontmatter aliases, external links, GitHub URL inference, keyboard-friendly
dashboard triage, Markdown import adapter presets, lifecycle webhooks, restore
smoke tests, and the screenshot gallery.

## 1. Publish the PyPI package with Trusted Publishing

GitHub issue: <https://github.com/xq520mmy/IssueDeck/issues/20>
Status: GitHub environment and `PYPI_PUBLISH=true` are configured. A manual
publish run reached PyPI and failed with `invalid-publisher`, which confirms
the remaining blocker is the PyPI pending publisher configuration.

Labels: `enhancement`, `area: deployment`, `area: docs`

IssueDeck can already be installed from GitHub with `uvx --from git+...`.
Publishing to PyPI will make the short `uvx issuedeck demo --open` path work
for new users.

Acceptance criteria:

- Configure the PyPI project `issuedeck` with Trusted Publishing for owner
  `xq520mmy`, repository `IssueDeck`, workflow `pypi-publish.yml`, and
  environment `pypi`.
- Enable the guarded publish path with the repository variable
  `PYPI_PUBLISH=true` or run the workflow manually against a release tag.
- Verify a fresh machine can run `uvx issuedeck demo --open`.
- Update README copy once the PyPI path is live.

## 2. Add a webhook receiver examples page

GitHub issue: <https://github.com/xq520mmy/IssueDeck/issues/26>
Status: implemented in `docs/webhook-receivers.md`.

Labels: `good first issue`, `enhancement`, `area: docs`

IssueDeck can send signed lifecycle webhooks, but new users still need
copy-pasteable receiver examples for common stacks.

Acceptance criteria:

- Add `docs/webhook-receivers.md`.
- Include minimal FastAPI, Flask, and Node/Express examples that verify the
  `X-IssueDeck-Signature` HMAC header.
- Link the page from `docs/webhooks.md` and README documentation links.
- Keep examples small and clearly mark secrets as placeholders.

## 3. Add a Docker Compose hardening example

GitHub issue: <https://github.com/xq520mmy/IssueDeck/issues/27>
Status: implemented in `docs/docker-compose-hardening.md`.

Labels: `good first issue`, `area: deployment`, `area: docs`

The current Compose file is intentionally simple. A small hardening example
would help self-hosters understand the next step without turning IssueDeck into
a platform project.

Acceptance criteria:

- Add a documented example under `deploy/` or `docs/` that shows pinned image
  tags, persistent volumes, health checks, backup scheduling notes, and reverse
  proxy assumptions.
- Link it from `DEPLOY.md` and `docs/deployment.zh.md`.
- Do not introduce a new required runtime dependency.

## 4. Add a dashboard accessibility smoke checklist

GitHub issue: <https://github.com/xq520mmy/IssueDeck/issues/28>
Status: implemented in `docs/accessibility-checklist.md`.

Labels: `good first issue`, `area: dashboard`, `area: docs`

IssueDeck already has keyboard-friendly dashboard flows. A lightweight
accessibility checklist would make future UI work easier to review.

Acceptance criteria:

- Add `docs/accessibility-checklist.md`.
- Cover keyboard navigation, focus visibility, labels, form errors, contrast,
  language switching, and responsive layout checks.
- Link it from `CONTRIBUTING.md` near the design workflow.
