"""Signed lifecycle webhook delivery."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel

from issuedeck.core.config import WebhookConfig, WebhookEvent

log = logging.getLogger("issuedeck.webhooks")

SleepFn = Callable[[float], Awaitable[Any]]


def build_webhook_payload(
    event: WebhookEvent,
    item: BaseModel,
    *,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    return {
        "event": event,
        "occurred_at": occurred_at or datetime.now(UTC).isoformat(),
        "item": item.model_dump(mode="json"),
    }


def encode_webhook_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def webhook_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def build_webhook_headers(
    webhook: WebhookConfig,
    event: WebhookEvent,
    body: bytes,
    *,
    delivery_id: str | None = None,
) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "User-Agent": "IssueDeck",
        "X-IssueDeck-Event": event,
        "X-IssueDeck-Delivery": delivery_id or str(uuid4()),
        "X-IssueDeck-Signature": webhook_signature(
            webhook.secret.get_secret_value(),
            body,
        ),
    }


async def deliver_webhook(
    webhook: WebhookConfig,
    payload: dict[str, Any],
    event: WebhookEvent,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    sleep: SleepFn = asyncio.sleep,
) -> bool:
    body = encode_webhook_body(payload)
    headers = build_webhook_headers(webhook, event, body)
    timeout = httpx.Timeout(webhook.timeout_seconds)
    attempts = webhook.retries + 1

    async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
        for attempt in range(attempts):
            try:
                response = await client.post(webhook.url, content=body, headers=headers)
                if 200 <= response.status_code < 300:
                    return True
                log.warning(
                    "webhook '%s' returned HTTP %s for %s",
                    webhook.name,
                    response.status_code,
                    event,
                )
            except httpx.HTTPError as exc:
                log.warning(
                    "webhook '%s' delivery failed for %s: %s",
                    webhook.name,
                    event,
                    exc.__class__.__name__,
                )

            if attempt < attempts - 1 and webhook.backoff_seconds > 0:
                await sleep(webhook.backoff_seconds * (2**attempt))

    return False


class WebhookDispatcher:
    def __init__(self, webhooks: list[WebhookConfig]) -> None:
        self._webhooks = webhooks

    def emit(self, event: WebhookEvent, item: BaseModel) -> None:
        targets = [webhook for webhook in self._webhooks if event in webhook.events]
        if not targets:
            return
        payload = build_webhook_payload(event, item)
        for webhook in targets:
            asyncio.create_task(self._deliver_safe(webhook, payload, event))

    async def _deliver_safe(
        self,
        webhook: WebhookConfig,
        payload: dict[str, Any],
        event: WebhookEvent,
    ) -> None:
        delivered = await deliver_webhook(webhook, payload, event)
        if not delivered:
            log.warning("webhook '%s' exhausted retries for %s", webhook.name, event)
