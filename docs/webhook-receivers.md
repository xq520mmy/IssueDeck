# Webhook Receiver Examples

[简体中文](webhook-receivers.zh-CN.md)

IssueDeck signs every lifecycle webhook with HMAC-SHA256. Receivers should
verify the signature against the raw request body before parsing JSON or doing
any work.

## Verification Rules

- Read the raw request body bytes.
- Compute `sha256=<hex-hmac>` with the shared webhook secret.
- Compare the computed value with `X-IssueDeck-Signature` using a constant-time
  comparison.
- Only parse JSON after the signature passes.
- Return any `2xx` status when the event has been accepted. IssueDeck retries
  non-`2xx` responses.

## FastAPI

```python
import hashlib
import hmac
import os

from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI()
SECRET = os.environ["ISSUEDECK_WEBHOOK_SECRET"]


def verify_signature(raw_body: bytes, signature: str | None) -> None:
    expected = "sha256=" + hmac.new(
        SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        raise HTTPException(status_code=401, detail="invalid signature")


@app.post("/hooks/issuedeck")
async def issuedeck_hook(
    request: Request,
    x_issuedeck_signature: str | None = Header(default=None),
    x_issuedeck_event: str | None = Header(default=None),
    x_issuedeck_delivery: str | None = Header(default=None),
) -> dict[str, bool]:
    raw_body = await request.body()
    verify_signature(raw_body, x_issuedeck_signature)
    payload = await request.json()

    print(
        "accepted",
        x_issuedeck_event,
        x_issuedeck_delivery,
        payload["item"]["local_id"],
    )
    return {"ok": True}
```

## Flask

```python
import hashlib
import hmac
import os

from flask import Flask, abort, request

app = Flask(__name__)
SECRET = os.environ["ISSUEDECK_WEBHOOK_SECRET"]


def verify_signature(raw_body: bytes, signature: str | None) -> None:
    expected = "sha256=" + hmac.new(
        SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        abort(401)


@app.post("/hooks/issuedeck")
def issuedeck_hook():
    raw_body = request.get_data(cache=True)
    verify_signature(raw_body, request.headers.get("X-IssueDeck-Signature"))
    payload = request.get_json()

    app.logger.info(
        "accepted %s delivery=%s item=%s",
        request.headers.get("X-IssueDeck-Event"),
        request.headers.get("X-IssueDeck-Delivery"),
        payload["item"]["local_id"],
    )
    return "", 204
```

## Node / Express

```js
import crypto from "node:crypto";
import express from "express";

const app = express();
const secret = process.env.ISSUEDECK_WEBHOOK_SECRET;

function expectedSignature(rawBody) {
  const digest = crypto
    .createHmac("sha256", secret)
    .update(rawBody)
    .digest("hex");
  return `sha256=${digest}`;
}

function safeEqual(left, right) {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right || "");
  return (
    leftBuffer.length === rightBuffer.length &&
    crypto.timingSafeEqual(leftBuffer, rightBuffer)
  );
}

app.post(
  "/hooks/issuedeck",
  express.raw({ type: "application/json" }),
  (req, res) => {
    const expected = expectedSignature(req.body);
    const signature = req.header("X-IssueDeck-Signature");
    if (!safeEqual(expected, signature)) {
      return res.sendStatus(401);
    }

    const payload = JSON.parse(req.body.toString("utf8"));
    console.log("accepted", {
      event: req.header("X-IssueDeck-Event"),
      delivery: req.header("X-IssueDeck-Delivery"),
      item: payload.item.local_id,
    });
    return res.sendStatus(204);
  },
);

app.listen(3000);
```

Use `express.raw()` for this route. If `express.json()` runs first, the
original bytes may be unavailable and signature verification can fail.

## IssueDeck Configuration

Point `server.toml` at the receiver URL and use the same secret in both places:

```toml
[[webhooks]]
name = "automation"
url = "https://example.com/hooks/issuedeck"
secret = "replace-with-a-long-random-secret"
events = ["item.created", "item.updated", "item.shipped"]
retries = 3
timeout_seconds = 5
backoff_seconds = 0.5
```

If the receiver runs on the Docker host while IssueDeck runs in Docker Desktop,
`http://host.docker.internal:3000/hooks/issuedeck` is often the right local URL.
In a Compose network, use the service name instead.

## Troubleshooting

- `401`: confirm both processes use the same secret and that the receiver signs
  the raw body bytes.
- No delivery: confirm the webhook URL is reachable from the IssueDeck server,
  not just from your browser.
- Repeated retries: return a `2xx` response after enqueueing the event.
- Duplicate handling: use `X-IssueDeck-Delivery` as an idempotency key when
  writing to downstream systems.
