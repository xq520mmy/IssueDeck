# GitHub URL Import

[简体中文](github-import.zh-CN.md)

`issuedeck import-github-url` creates an IssueDeck item from a GitHub issue,
pull request, or commit URL. It is intentionally not a sync engine: it does not
call the GitHub API, mirror comments, or keep state up to date. It creates one
local item with a normalized external link so the work can be tracked in
IssueDeck.

## Create an Item

```bash
uv run issuedeck import-github-url \
  --config server.toml \
  --project-key example \
  --kind feature \
  https://github.com/example/repo/issues/42
```

The command infers:

- `github_issue`, `github_pr`, or `github_commit`
- A stable GitHub URL without query parameters
- A default title such as `Review GitHub issue #42 from example/repo`
- A default `github` tag
- A body that points back to the source URL

## Preview First

Use `--dry-run` to print the create payload without writing to SQLite:

```bash
uv run issuedeck import-github-url \
  --config server.toml \
  --project-key example \
  --kind bug \
  --dry-run \
  https://github.com/example/repo/issues/42
```

## Options

- `--kind`: IssueDeck kind to create. If omitted, IssueDeck uses the first kind
  in the project config.
- `--title`: override the generated title.
- `--body`: override the generated body.
- `--tag`: add a tag. Repeat for multiple tags.
- `--applies-to`: target a branch. Repeat for multiple branches.
- `--link-label`: override the external link label.

## Examples

Pull request:

```bash
uv run issuedeck import-github-url \
  --config server.toml \
  --project-key example \
  --kind improvement \
  --tag upstream \
  https://github.com/example/repo/pull/7
```

Commit:

```bash
uv run issuedeck import-github-url \
  --config server.toml \
  --project-key example \
  --kind feature \
  --title "Review upstream fix" \
  https://github.com/example/repo/commit/abc1234def
```

## When to Use It

Use this helper when you want a local IssueDeck item for something that already
exists on GitHub, but you do not need a full GitHub integration. For full issue
mirroring, label synchronization, or comment imports, keep that as a separate
integration layer.
