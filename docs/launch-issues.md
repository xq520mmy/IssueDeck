# Starter Issue Backlog

These are candidate public issues for the next open-source iterations. The
original launch backlog has mostly shipped: one-command demo mode, MCP client
examples, scoped tokens, saved dashboard filters, Markdown frontmatter aliases,
external links, GitHub URL inference, keyboard-friendly dashboard triage,
restore smoke tests, and the screenshot gallery.

## 1. Publish the PyPI package with Trusted Publishing

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

## 2. Add Markdown import adapter presets

Labels: `enhancement`, `help wanted`, `area: migration`

The frontmatter importer supports common aliases today, but teams often have
their own Markdown issue shapes. Adapter presets would make migration less
manual.

Acceptance criteria:

- Add named presets for at least two common Markdown tracker shapes.
- Keep the default importer behavior unchanged.
- Include fixtures that cover status, kind, tags, branch/applicability, and
  external links.
- Document how to pick a preset and how to override fields.

## 3. Add lifecycle webhooks

Labels: `enhancement`, `help wanted`, `area: integrations`

Teams may want lightweight notifications or automation when items change state,
are shipped, or are restored.

Acceptance criteria:

- Emit webhook payloads for item created, item updated, item shipped, item
  deleted, and item restored events.
- Support signed requests with a shared secret.
- Include retry/backoff behavior that cannot block the main item mutation.
- Add tests for payload shape and signature verification.
