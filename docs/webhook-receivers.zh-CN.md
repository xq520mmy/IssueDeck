# Webhook Receiver 示例

[English](webhook-receivers.md)

IssueDeck 会用 HMAC-SHA256 给每个生命周期 Webhook 签名。Receiver 应该先用原始
request body 校验签名，签名通过后再解析 JSON 或执行后续自动化。

## 校验规则

- 读取原始 request body bytes。
- 使用共享 webhook secret 计算 `sha256=<hex-hmac>`。
- 用常量时间比较结果和 `X-IssueDeck-Signature`。
- 签名通过后再解析 JSON。
- 事件已接收时返回任意 `2xx` 状态码。非 `2xx` 响应会触发 IssueDeck 重试。

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

这个路由要使用 `express.raw()`。如果先经过 `express.json()`，原始 body bytes
可能已经不可用，签名校验会失败。

## IssueDeck 配置

在 `server.toml` 中指向 receiver URL，并让两端使用同一个 secret：

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

如果 receiver 运行在 Docker host，而 IssueDeck 运行在 Docker Desktop 中，本地调试
时通常可以使用 `http://host.docker.internal:3000/hooks/issuedeck`。如果两者在同一个
Compose network 中，使用 service name。

## 排查

- `401`：确认两端使用同一个 secret，并且 receiver 用原始 body bytes 计算签名。
- 没有投递：确认 webhook URL 对 IssueDeck server 可达，而不是只对浏览器可达。
- 反复重试：事件入队或接收后返回 `2xx`。
- 重复处理：写入下游系统时，可以把 `X-IssueDeck-Delivery` 作为幂等 key。
