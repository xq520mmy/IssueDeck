# Starter Issue Backlog

These are candidate public issues for the next open-source iterations. The
original launch backlog has mostly shipped: one-command demo mode, MCP client
examples, scoped tokens, saved dashboard filters, Markdown frontmatter aliases,
external links, restore smoke tests, and the screenshot gallery.

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

## 2. Add GitHub URL import helpers for external links

Labels: `enhancement`, `help wanted`, `area: integrations`, `area: dashboard`

IssueDeck already stores external links for GitHub issues, pull requests, and
commits. The next polish step is making pasted GitHub URLs easier to turn into
structured links.

Acceptance criteria:

- Accept a GitHub issue, pull request, or commit URL and infer `link_type`,
  label, and normalized URL.
- Use the helper from the dashboard item form and from an API/MCP-friendly
  utility path.
- Keep the feature optional and avoid requiring GitHub authentication.
- Add tests for issue, pull request, commit, and non-GitHub URLs.

## 3. Add keyboard-friendly dashboard triage

Labels: `enhancement`, `design`, `area: dashboard`

The list and kanban views should feel fast for repeated review sessions, not
only for point-and-click browsing.

Acceptance criteria:

- Add keyboard actions for common triage moves such as focusing search,
  opening filters, creating an item, and moving between list results.
- Keep shortcuts inactive while the user is typing in inputs, textareas, or
  content-editable fields.
- Add accessibility labels and tests for the scripted behavior.
- Document the shortcut map outside the main dashboard UI.

## 4. Add Markdown import adapter presets

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

## 5. Add lifecycle webhooks

Labels: `enhancement`, `help wanted`, `area: integrations`

Teams may want lightweight notifications or automation when items change state,
are shipped, or are restored.

Acceptance criteria:

- Emit webhook payloads for item created, item updated, item shipped, item
  deleted, and item restored events.
- Support signed requests with a shared secret.
- Include retry/backoff behavior that cannot block the main item mutation.
- Add tests for payload shape and signature verification.

## 6. Improve first-run troubleshooting docs

Labels: `documentation`, `good first issue`, `area: docs`

The happy path is short, but first-time users still need clear recovery notes
for local environment problems.

Acceptance criteria:

- Add troubleshooting notes for missing `uv`, occupied ports, invalid tokens,
  SQLite migration errors, and Docker Compose startup failures.
- Include Windows PowerShell examples where commands differ.
- Link the troubleshooting section from README and SUPPORT.
