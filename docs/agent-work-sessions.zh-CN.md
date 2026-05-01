# Agent 工作会话

Agent Work Sessions 让 IssueDeck 不只是事项列表，也能成为 AI coding 工作的
控制台。一个会话会记录哪个 agent 正在处理哪个事项、目标是什么、最近进展、
以及最后如何结束。

## 什么时候使用

当 agent 开始真实实现、排查或 review 某个 IssueDeck item 时，就可以创建一个
work session。Item activity timeline 仍然记录关键事件，而 session 负责展示
当前工作状态。

## Dashboard

- 项目总览会显示活跃和暂停中的 Agent 会话。
- Item 详情页会显示该事项的全部会话，包括状态、目标、分支、更新次数和最终总结。
- Demo 数据内置活跃和已完成会话，公开截图不会暴露真实项目内容。

## REST API

开始会话：

```bash
curl -X POST http://127.0.0.1:8765/api/v1/projects/example/work-sessions \
  -H "Authorization: Bearer issuedeck-local-token" \
  -H "Content-Type: application/json" \
  -d '{
    "local_id": "FEAT-0001",
    "agent_name": "codex",
    "goal": "Implement dashboard session visibility.",
    "branch": "main"
  }'
```

追加进展：

```bash
curl -X POST http://127.0.0.1:8765/api/v1/projects/example/work-sessions/1/updates \
  -H "Authorization: Bearer issuedeck-local-token" \
  -H "Content-Type: application/json" \
  -d '{"message": "REST and MCP routes are wired.", "update_type": "progress"}'
```

完成会话：

```bash
curl -X POST http://127.0.0.1:8765/api/v1/projects/example/work-sessions/1/finish \
  -H "Authorization: Bearer issuedeck-local-token" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "summary": "Shipped the feature."}'
```

列出会话：

```bash
curl "http://127.0.0.1:8765/api/v1/projects/example/work-sessions?status=active" \
  -H "Authorization: Bearer issuedeck-local-token"
```

## MCP Tools

Agent 可以直接调用这些工具：

- `start_work_session`
- `update_work_session`
- `finish_work_session`
- `list_work_sessions`
- `get_work_session`

Session API 也会写入 item activity events，例如 `work_session_started`、
`work_session_updated` 和 `work_session_completed`，所以人可以从 session 列表或
item timeline 两个入口跟进工作。

