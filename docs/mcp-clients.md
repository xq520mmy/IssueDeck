# MCP Client Setup

IssueDeck ships a local stdio MCP server for coding agents. The MCP process is
only a client for the IssueDeck REST API: it reads `ISSUEDECK_BASE_URL` and
`ISSUEDECK_TOKEN`, sends HTTP requests to the running server, and never opens
SQLite directly.

## Start IssueDeck First

For a local trial, start the demo server:

```bash
uv run issuedeck demo
```

That command starts the REST API at `http://127.0.0.1:8765` and creates the
demo token `issuedeck-local-token` when it creates a fresh `server.toml`.

For an existing server, use your real dashboard/API token instead. The server
reads `ISSUEDECK_API_TOKEN`; the MCP process reads `ISSUEDECK_TOKEN`. In most
local setups they should have the same value, but they are separate environment
variables because the server and the client are different processes.

## Base Stdio Config

Most MCP clients accept a JSON object under `mcpServers`. Use an absolute path
for the cloned IssueDeck repo so the client can launch the server from any
working directory.

```json
{
  "mcpServers": {
    "issuedeck": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/IssueDeck",
        "run",
        "python",
        "-m",
        "issuedeck.mcp"
      ],
      "env": {
        "ISSUEDECK_BASE_URL": "http://127.0.0.1:8765",
        "ISSUEDECK_TOKEN": "replace-with-your-server-token"
      }
    }
  }
}
```

If `uv` is not on the client's `PATH`, replace `"uv"` with the absolute path
from `which uv` on macOS/Linux or `where uv` on Windows. On Windows, JSON paths
can use forward slashes or escaped backslashes.

## Claude Desktop

Open Claude Desktop settings, go to the developer section, edit the MCP config,
and add IssueDeck under `mcpServers`.

```json
{
  "mcpServers": {
    "issuedeck": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/IssueDeck",
        "run",
        "python",
        "-m",
        "issuedeck.mcp"
      ],
      "env": {
        "ISSUEDECK_BASE_URL": "http://127.0.0.1:8765",
        "ISSUEDECK_TOKEN": "replace-with-your-server-token"
      }
    }
  }
}
```

Save the file and restart Claude Desktop. Keep IssueDeck's REST server running
while you use the tools.

## Claude Code

Claude Code can add a stdio server directly from JSON:

```bash
claude mcp add-json issuedeck '{"type":"stdio","command":"uv","args":["--directory","/absolute/path/to/IssueDeck","run","python","-m","issuedeck.mcp"],"env":{"ISSUEDECK_BASE_URL":"http://127.0.0.1:8765","ISSUEDECK_TOKEN":"replace-with-your-server-token"}}'
claude mcp get issuedeck
```

Use `--scope user` if you want the server available outside the current
project.

## Cursor

For project-scoped tools, create `.cursor/mcp.json`. For global tools, create
`~/.cursor/mcp.json`.

```json
{
  "mcpServers": {
    "issuedeck": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/IssueDeck",
        "run",
        "python",
        "-m",
        "issuedeck.mcp"
      ],
      "env": {
        "ISSUEDECK_BASE_URL": "http://127.0.0.1:8765",
        "ISSUEDECK_TOKEN": "replace-with-your-server-token"
      }
    }
  }
}
```

In Cursor CLI, verify the connection with:

```bash
cursor-agent mcp list
cursor-agent mcp list-tools issuedeck
```

In the Cursor editor, open the Tools & MCP settings and confirm that IssueDeck
appears as an available stdio server.

## Smoke Test Prompt

After the client sees the tools, ask:

```text
Use IssueDeck to list projects, then list the latest items in the example project.
```

For the demo server, the project key is `example`. For a real project, use the
key from its `projects/<key>.toml` file.

## Troubleshooting

- `ISSUEDECK_TOKEN` must match the server token. For the demo flow, that token
  is `issuedeck-local-token`.
- Keep the REST server running. MCP starts a stdio helper process, not the
  IssueDeck web server.
- If the client cannot launch `uv`, use an absolute executable path.
- If tools connect but return authorization errors, confirm that the server was
  started with the same token that the MCP config passes as `ISSUEDECK_TOKEN`.
- If tools connect but return project errors, verify the project key exists in
  the server's `projects_dir`.

## References

- [Model Context Protocol server guide](https://modelcontextprotocol.io/docs/develop/build-server)
- [Claude Code MCP guide](https://code.claude.com/docs/en/mcp)
- [Cursor MCP guide](https://docs.cursor.com/context/model-context-protocol)
- [Cursor CLI MCP guide](https://docs.cursor.com/cli/mcp)
