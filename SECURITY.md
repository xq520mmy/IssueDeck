# Security Policy

## Supported Versions

IssueDeck is currently pre-1.0. Security fixes target the latest `main` branch
and the latest public release until a stable release line exists.

| Version | Supported |
| --- | --- |
| `0.2.x` | Yes |
| `< 0.2.0` | No |

## Reporting a Vulnerability

Please do not open a public issue for sensitive vulnerabilities.

If this repository has a private security advisory channel enabled, use that.
Otherwise, contact the maintainers privately through the repository owner.

Include:

- A clear description of the issue.
- Reproduction steps or a proof of concept.
- Affected version or commit SHA.
- Whether the issue requires authentication.
- Any known workaround.

## Security Model

IssueDeck currently uses a shared bearer token for the REST API and MCP client.
The dashboard login form validates the same server token and then stores a
signed, HTTP-only browser session cookie. Treat `ISSUEDECK_API_TOKEN` and
`ISSUEDECK_TOKEN` as secrets.

Do not commit:

- `.env` files.
- `server.toml` with real tokens.
- `projects/*.toml` containing private project metadata.
- `data/tracker.db` or backups.
- generated Docker image archives.

For production or team deployments, run behind a trusted network boundary or
reverse proxy, rotate shared tokens when people leave the team, and back up the
SQLite database regularly.
