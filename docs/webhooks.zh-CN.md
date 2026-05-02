# 生命周期 Webhooks

IssueDeck 可以在事项创建、更新、发布、删除、恢复时发送带签名的异步
Webhook。Webhook 投递失败会在后台重试，不会阻塞主流程里的创建、更新、
发布、删除或恢复请求。

## 配置

在 `server.toml` 中加入一个或多个 `[[webhooks]]`：

```toml
[[webhooks]]
name = "automation"
url = "https://example.com/hooks/issuedeck"
secret = "replace-with-a-long-random-secret"
events = [
  "item.created",
  "item.updated",
  "item.shipped",
  "item.deleted",
  "item.restored",
]
retries = 3
timeout_seconds = 5
backoff_seconds = 0.5
```

如果省略 `events`，IssueDeck 会发送全部生命周期事件。`retries` 表示首次投递
失败后的重试次数。

## 团队通知

如果目标是给人看的一条聊天提醒，而不是给系统消费的签名结构化 payload，可以
使用 `[[notifications]]`。IssueDeck 目前支持 Slack 和 Discord incoming
webhook URL：

```toml
[[notifications]]
name = "team-alerts"
provider = "slack"
url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXX"
events = ["item.created", "item.shipped"]
retries = 3
timeout_seconds = 5
backoff_seconds = 0.5

[[notifications]]
name = "release-room"
provider = "discord"
url = "https://discord.com/api/webhooks/1234567890/replace-with-token"
events = ["item.shipped"]
```

Slack 通知会向 incoming webhook URL 发送 `{"text": "..."}`。Discord 通知会
发送 `{"content": "...", "allowed_mentions": {"parse": []}}`，避免事项标题意外
触发频道提醒。通知 URL 属于 secret，应该放在本地部署配置中，不要提交到公开仓库。

## 邮件通知

如果团队更依赖邮箱或运维邮件流，可以使用 `[[email_notifications]]`：

```toml
[[email_notifications]]
name = "ops-inbox"
smtp_host = "smtp.example.com"
smtp_port = 587
smtp_security = "starttls" # starttls、ssl 或 none
username = "issuebot"
password = "replace-with-smtp-password"
from_email = "issuebot@example.com"
to_emails = ["ops@example.com", "dev@example.com"]
subject_prefix = "[IssueDeck]"
events = ["item.created", "item.shipped"]
retries = 3
timeout_seconds = 10
backoff_seconds = 0.5
```

`username` 和 `password` 是可选项，但 SMTP 需要认证时必须同时设置。密码属于
secret，应该只放在部署本地配置里。

## 事件

- `item.created`
- `item.updated`
- `item.shipped`
- `item.deleted`
- `item.restored`

## Payload

```json
{
  "event": "item.shipped",
  "occurred_at": "2026-04-29T01:00:00+00:00",
  "item": {
    "project_key": "example",
    "local_id": "FEAT-0001",
    "kind": "feature",
    "status": "done",
    "title": "Add webhook automation",
    "body_preview": "Notify downstream tools...",
    "tags": ["integration"],
    "applies_to": ["main"],
    "external_links": [],
    "created_at": "2026-04-29T00:00:00+00:00",
    "updated_at": "2026-04-29T01:00:00+00:00",
    "deleted_at": null
  }
}
```

签名前，IssueDeck 会使用稳定 key 顺序编码 JSON body。

## 请求头

每次请求都会包含：

- `X-IssueDeck-Event`：生命周期事件名。
- `X-IssueDeck-Delivery`：唯一投递 ID。
- `X-IssueDeck-Signature`：`sha256=<hex-hmac>`，用 webhook secret 和原始
  request body 计算。

Python 校验示例：

```python
import hashlib
import hmac

expected = "sha256=" + hmac.new(
    secret.encode("utf-8"),
    raw_body,
    hashlib.sha256,
).hexdigest()

if not hmac.compare_digest(expected, request.headers["X-IssueDeck-Signature"]):
    raise ValueError("invalid IssueDeck webhook signature")
```

FastAPI、Flask、Node/Express 的完整 receiver 示例见
[Webhook Receiver 示例](webhook-receivers.zh-CN.md)。

## 投递行为

IssueDeck 会在事项变更事务提交后启动 Webhook 投递。慢响应或失败的端点只会被
记录日志并按指数退避重试，不会影响 API 或 Dashboard 请求。
