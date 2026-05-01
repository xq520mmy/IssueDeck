# Agent Work Sessions

Agent Work Sessions make IssueDeck useful as a control plane for AI coding
work. A session records which agent is working on an item, what the goal is,
recent progress, and how the work ended.

## When To Use

Use a work session when an agent starts real implementation, investigation, or
review work on an IssueDeck item. The item activity timeline still records the
important events, while the session keeps the running state visible on the
dashboard.

## Dashboard

- Project overview shows active and paused agent sessions.
- Item detail shows all sessions for that item, including status, goal, branch,
  update count, and final summary.
- Demo data includes both active and completed sessions so screenshots can show
  the workflow without private project data.

## REST API

Start a session:

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

Append progress:

```bash
curl -X POST http://127.0.0.1:8765/api/v1/projects/example/work-sessions/1/updates \
  -H "Authorization: Bearer issuedeck-local-token" \
  -H "Content-Type: application/json" \
  -d '{"message": "REST and MCP routes are wired.", "update_type": "progress"}'
```

Finish a session:

```bash
curl -X POST http://127.0.0.1:8765/api/v1/projects/example/work-sessions/1/finish \
  -H "Authorization: Bearer issuedeck-local-token" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "summary": "Shipped the feature."}'
```

List sessions:

```bash
curl "http://127.0.0.1:8765/api/v1/projects/example/work-sessions?status=active" \
  -H "Authorization: Bearer issuedeck-local-token"
```

## MCP Tools

Agents can call these tools directly:

- `start_work_session`
- `update_work_session`
- `finish_work_session`
- `list_work_sessions`
- `get_work_session`

The session API also writes item activity events such as
`work_session_started`, `work_session_updated`, and `work_session_completed`,
so humans can follow the work from either the session list or the item timeline.

