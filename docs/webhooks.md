# Lifecycle Webhooks

IssueDeck can deliver signed, asynchronous webhooks when items move through
their lifecycle. Webhook failures are retried in the background and do not block
the item create, update, ship, delete, or restore request.

## Configure

Add one or more `[[webhooks]]` blocks to `server.toml`:

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

If `events` is omitted, IssueDeck sends all lifecycle events. `retries` is the
number of retry attempts after the first delivery attempt.

## Team Notifications

Use `[[notifications]]` when humans need a simple chat update instead of a
signed machine-readable webhook payload. IssueDeck currently supports Slack and
Discord incoming webhook URLs:

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

Slack notifications send `{"text": "..."}` to the incoming webhook URL.
Discord notifications send `{"content": "...", "allowed_mentions": {"parse":
[]}}` so issue titles cannot accidentally ping a channel. Notification URLs are
secrets; store them in local deployment config, not in public repositories.

## Events

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

The JSON body is encoded with stable key ordering before signing.

## Headers

Each request includes:

- `X-IssueDeck-Event`: lifecycle event name.
- `X-IssueDeck-Delivery`: unique delivery id.
- `X-IssueDeck-Signature`: `sha256=<hex-hmac>` using the webhook secret and
  raw request body.

Python verification example:

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

For complete receiver examples in FastAPI, Flask, and Node/Express, see
[Webhook Receiver Examples](webhook-receivers.md).

## Delivery Behavior

IssueDeck starts webhook delivery after the item mutation commits. A failing or
slow webhook endpoint is logged, retried with exponential backoff, and isolated
from the main API or dashboard request.
