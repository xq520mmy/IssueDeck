# Starter Issue Backlog

These are candidate public issues for the next open-source iterations. The
original launch backlog has mostly shipped: one-command demo mode, MCP client
examples, scoped tokens, saved dashboard filters, Markdown frontmatter aliases,
external links, GitHub URL inference, keyboard-friendly dashboard triage,
Markdown import adapter presets, lifecycle webhooks, restore smoke tests, and
the screenshot gallery.

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
