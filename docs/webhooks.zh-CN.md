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
