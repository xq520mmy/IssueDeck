# MCP 客户端接入

IssueDeck 内置一个本地 stdio MCP server，方便 coding agent 直接操作事项。
这个 MCP 进程只是 IssueDeck REST API 的客户端：它读取 `ISSUEDECK_BASE_URL`
和 `ISSUEDECK_TOKEN`，通过 HTTP 调用正在运行的 IssueDeck server，不会直接打开
SQLite。

## 先启动 IssueDeck

本地体验可以直接启动 demo：

```bash
uv run issuedeck demo
```

这个命令会把 REST API 跑在 `http://127.0.0.1:8765`，如果它新建了
`server.toml`，默认本地 token 是 `issuedeck-local-token`。

已有服务请使用真实的 dashboard/API token。服务端读取 `ISSUEDECK_API_TOKEN`；
MCP 进程读取 `ISSUEDECK_TOKEN`。本地场景里它们通常是同一个值，但两个变量名
刻意分开，因为服务端和客户端是两个不同进程。

生产环境建议给 MCP 客户端单独配置 `scopes = ["agent"]` 的 IssueDeck token。
它可以读写 REST API，但不能登录 Dashboard。

## 通用 stdio 配置

多数 MCP 客户端都接受 `mcpServers` JSON 配置。建议使用 IssueDeck 仓库的绝对
路径，这样客户端从任何工作目录启动都不会找错项目。

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

如果客户端找不到 `uv`，把 `"uv"` 换成可执行文件绝对路径。macOS/Linux 可用
`which uv`，Windows 可用 `where uv`。Windows 的 JSON 路径可以使用正斜杠，
也可以使用转义后的反斜杠。

## Claude Desktop

打开 Claude Desktop 设置，在 developer 区域编辑 MCP config，把 IssueDeck
加入 `mcpServers`。

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

保存后重启 Claude Desktop。使用工具时，IssueDeck 的 REST server 需要保持运行。

## Claude Code

Claude Code 可以直接从 JSON 添加 stdio server：

```bash
claude mcp add-json issuedeck '{"type":"stdio","command":"uv","args":["--directory","/absolute/path/to/IssueDeck","run","python","-m","issuedeck.mcp"],"env":{"ISSUEDECK_BASE_URL":"http://127.0.0.1:8765","ISSUEDECK_TOKEN":"replace-with-your-server-token"}}'
claude mcp get issuedeck
```

如果希望在所有项目里都可用，可以加 `--scope user`。

## Cursor

项目级工具创建 `.cursor/mcp.json`。全局工具创建 `~/.cursor/mcp.json`。

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

Cursor CLI 可以这样验证：

```bash
cursor-agent mcp list
cursor-agent mcp list-tools issuedeck
```

在 Cursor 编辑器里，可以打开 Tools & MCP 设置，确认 IssueDeck 显示为可用的
stdio server。

## Agent 工作会话

当 agent 开始处理一个实质性 item 时，可以让它先调用 `start_work_session`，
过程中用 `update_work_session` 追加进展，最后用 `finish_work_session` 收尾。
Dashboard 会在项目总览展示活跃会话，也会在 item 详情页展示会话历史。

## 冒烟测试提示词

客户端能看到工具后，可以问：

```text
Use IssueDeck to list projects, then list the latest items in the example project.
```

demo server 的项目 key 是 `example`。真实项目请使用 `projects/<key>.toml`
里的 key。

## 排障

- `ISSUEDECK_TOKEN` 必须和服务端 token 一致。demo 流程默认是
  `issuedeck-local-token`。
- REST server 需要保持运行。MCP 会启动 stdio helper 进程，但不会自动启动
  IssueDeck web server。
- 如果客户端找不到 `uv`，请使用 `uv` 可执行文件的绝对路径。
- 如果工具能连接但返回鉴权错误，检查服务端 token 是否和 MCP 配置里的
  `ISSUEDECK_TOKEN` 一致。
- 如果工具能连接但返回项目错误，检查 server 的 `projects_dir` 中是否存在该
  project key。

## 参考

- [Model Context Protocol server guide](https://modelcontextprotocol.io/docs/develop/build-server)
- [Claude Code MCP guide](https://code.claude.com/docs/en/mcp)
- [Cursor MCP guide](https://docs.cursor.com/context/model-context-protocol)
- [Cursor CLI MCP guide](https://docs.cursor.com/cli/mcp)
