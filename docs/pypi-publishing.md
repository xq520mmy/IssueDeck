# PyPI Publishing

IssueDeck is ready for PyPI Trusted Publishing. This avoids long-lived PyPI API
tokens in GitHub secrets and uses GitHub Actions OIDC instead.

## Public Install Goal

After the PyPI project is published, users can try IssueDeck without cloning the
repository:

```bash
uvx issuedeck demo --open
```

Until the PyPI project exists, users can still run the latest GitHub version:

```bash
uvx --from git+https://github.com/xq520mmy/IssueDeck issuedeck demo --open
```

## One-time PyPI Setup

Create a pending publisher on PyPI:

- PyPI project name: `issuedeck`
- Owner: `xq520mmy`
- Repository: `IssueDeck`
- Workflow filename: `pypi-publish.yml`
- Environment name: `pypi`

The project name is not reserved until the first successful publish. If someone
else registers `issuedeck` before the first publish, the pending publisher will
no longer work.

## GitHub Setup

Create a GitHub environment named `pypi`. It does not need secrets for Trusted
Publishing. Optional protection rules are useful if releases should require a
manual reviewer.

For automatic publishing on future tags, add a repository variable:

```text
PYPI_PUBLISH=true
```

Without that variable, tag pushes build GitHub release assets but skip PyPI
upload. You can still publish manually from GitHub Actions by running
`pypi-publish` with a tag such as `v0.2.1`.

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

## Local Package Smoke Test

Before publishing, build and install the wheel in a clean virtual environment:

```powershell
python -m build
python -m venv .tmp-wheel-smoke
$wheel = Get-ChildItem dist\issuedeck-*.whl | Select-Object -First 1
.tmp-wheel-smoke\Scripts\python -m pip install $wheel.FullName
.tmp-wheel-smoke\Scripts\issuedeck --help
```
