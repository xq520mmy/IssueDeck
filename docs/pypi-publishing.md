# PyPI Publishing

IssueDeck is ready for PyPI Trusted Publishing. This avoids long-lived PyPI API
tokens in GitHub secrets and uses GitHub Actions OIDC instead.

## Public Install

IssueDeck is published on PyPI, so users can try it without cloning the
repository:

```bash
uvx issuedeck demo --open
```

To test unreleased changes from GitHub:

```bash
uvx --from git+https://github.com/xq520mmy/IssueDeck issuedeck demo --open
```

## One-time PyPI Setup

The canonical IssueDeck project has already completed this setup. For forks,
mirrors, or future project-name changes, create a pending publisher on PyPI:

- PyPI project name: `issuedeck`
- Owner: `xq520mmy`
- Repository: `IssueDeck`
- Workflow filename: `pypi-publish.yml`
- Environment name: `pypi`

The project name is not reserved until the first successful publish. After the
first successful publish, the pending publisher becomes a normal project
publisher.

## GitHub Setup

Create a GitHub environment named `pypi`. It does not need secrets for Trusted
Publishing. Optional protection rules are useful if releases should require a
manual reviewer.

For automatic publishing on future tags, add a repository variable. The
canonical IssueDeck repository already has this enabled; forks or new mirrors
need to configure it themselves:

```text
PYPI_PUBLISH=true
```

Without that variable, tag pushes build GitHub release assets but skip PyPI
upload. You can still publish manually from GitHub Actions by running
`pypi-publish` with a tag such as `v0.3.2`.

## Release Flow

1. Update `CHANGELOG.md` and version metadata.
2. Push `main` and confirm CI is green.
3. Push a `vX.Y.Z` tag.
4. Confirm `release-artifacts` created the GitHub Release assets.
5. Confirm `pypi-publish` uploaded the same wheel and sdist to PyPI.
6. Smoke test:

```bash
uvx issuedeck --help
uvx issuedeck demo --open
```

## Troubleshooting `invalid-publisher`

If the publish job fails with `invalid-publisher`, GitHub OIDC worked but PyPI
could not find a matching trusted publisher. Check the PyPI pending publisher
against the claims printed in the failed workflow log.

For this repository, the expected GitHub Actions claims are:

```text
sub: repo:xq520mmy/IssueDeck:environment:pypi
repository: xq520mmy/IssueDeck
repository_owner: xq520mmy
workflow: pypi-publish.yml
environment: pypi
```

The matching PyPI pending publisher should be:

- PyPI project name: `issuedeck`
- Owner: `xq520mmy`
- Repository: `IssueDeck`
- Workflow filename: `pypi-publish.yml`
- Environment name: `pypi`

After fixing the publisher configuration, rerun the `pypi-publish` workflow
with the release tag, for example `v0.3.2`.

## Local Package Smoke Test

Before publishing, build and install the wheel in a clean virtual environment:

```powershell
python -m build
python -m venv .tmp-wheel-smoke
$wheel = Get-ChildItem dist\issuedeck-*.whl | Select-Object -First 1
.tmp-wheel-smoke\Scripts\python -m pip install $wheel.FullName
.tmp-wheel-smoke\Scripts\issuedeck --help
```
